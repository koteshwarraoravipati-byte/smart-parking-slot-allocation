"""Destructive integration tests: ONLY point TEST_DATABASE_URL at a disposable database."""
import os
import pytest
from concurrent.futures import ThreadPoolExecutor

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL") or os.getenv("ALLOW_DESTRUCTIVE_TESTS") != "1", reason="Set TEST_DATABASE_URL to a disposable DB and ALLOW_DESTRUCTIVE_TESTS=1")
@pytest.fixture()
def setup():
    url = os.environ["TEST_DATABASE_URL"]
    if not url.startswith("postgresql"): pytest.fail("Integration tests require real PostgreSQL")
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("JWT_SECRET", "test-only-secret-" + "x" * 40)
    from app.models import Base, engine, Session, Slot, User
    from app.security import hash_password
    from app.main import app, _ticket_attempts
    _ticket_attempts.clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session.begin() as db:
        db.add_all([Slot(id=i,label=f"P-{i}",row=1,column=i) for i in range(1,4)])
        db.add_all([User(username=f"user{i}",password_hash=hash_password("password-for-tests"),role="user") for i in range(12)])
    with Session.begin() as db:
        db.add(User(username="operator",password_hash=hash_password("password-for-tests"),role="admin"))
    from sqlalchemy import text
    with Session.begin() as db:
        db.execute(text("SELECT setval(pg_get_serial_sequence('slots','id'), (SELECT MAX(id) FROM slots))"))
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        tokens=[client.post("/auth/login",json={"username":f"user{i}","password":"password-for-tests"}).json()["token"] for i in range(12)]
        yield client, tokens
    Base.metadata.drop_all(engine)

def headers(token): return {"Authorization":"Bearer "+token}
def test_concurrent_allocation(setup):
    client,tokens=setup
    def attempt(i): return client.post("/allocate",headers=headers(tokens[i]),json={"vehicle":f"CAR{i}","request_key":f"request-{i}"})
    with ThreadPoolExecutor(max_workers=12) as pool: responses=list(pool.map(attempt,range(12)))
    winners=[r.json() for r in responses if r.status_code==200]
    assert len(winners)==3
    assert len({b["slot_id"] for b in winners})==3
    assert all(r.status_code in (200,409) for r in responses)

def test_idempotency_checkout_and_ownership(setup):
    client,tokens=setup
    h=headers(tokens[0]);body={"vehicle":"CAR1","request_key":"same-request"}
    first=client.post("/allocate",headers=h,json=body).json()
    replay=client.post("/allocate",headers=h,json=body).json()
    assert first["id"]==replay["id"]
    assert client.post("/allocate",headers=h,json={**body,"vehicle":"OTHER"}).status_code==409
    assert client.post("/allocate",headers=h,json={**body,"request_key":"new-request"}).status_code==409
    assert client.post(f"/bookings/{first['id']}/checkout",headers=headers(tokens[1])).status_code==403
    one=client.post(f"/bookings/{first['id']}/checkout",headers=h).json()
    two=client.post(f"/bookings/{first['id']}/checkout",headers=h).json()
    assert one==two and one["amount_cents"]==2000
    assert client.post("/allocate",headers=h,json={**body,"request_key":"after-checkout"}).status_code==200
    assert client.get("/admin/dashboard",headers=h).status_code==403
    assert client.get("/slots").status_code in (401,403)

def test_same_user_concurrency(setup):
    client,tokens=setup
    def attempt(i): return client.post("/allocate",headers=headers(tokens[0]),json={"vehicle":"CAR1","request_key":f"parallel-{i}"})
    with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(attempt,range(8)))
    assert sum(r.status_code==200 for r in results)==1

def admin_headers(client):
    response=client.post("/auth/login", json={"username":"operator","password":"password-for-tests"})
    assert response.status_code == 200
    return headers(response.json()["token"])

def test_slot_admin_validation_audit_and_access(setup):
    client,tokens=setup
    h=admin_headers(client)
    body={"label":"B-1","zone":"B","row":1,"column":1,"enabled":True,"maintenance_note":""}
    assert client.post("/admin/slots",headers=headers(tokens[0]),json=body).status_code==403
    assert client.patch("/admin/slots/1",headers=headers(tokens[0]),json={"version":1,"enabled":False}).status_code==403
    assert client.post("/admin/slots",json=body).status_code in (401,403)
    created=client.post("/admin/slots",headers=h,json=body)
    assert created.status_code==201
    slot=created.json()
    assert slot["available"] and not slot["occupied"] and slot["version"]==1
    assert client.post("/admin/slots",headers=h,json=body).status_code==409
    assert client.post("/admin/slots",headers=h,json={**body,"label":"OTHER"}).status_code==409
    assert client.patch(f"/admin/slots/{slot['id']}",headers=h,json={"enabled":False}).status_code==422
    assert client.patch(f"/admin/slots/{slot['id']}",headers=h,json={"version":1,"enabled":None}).status_code==422
    changed=client.patch(f"/admin/slots/{slot['id']}",headers=h,json={"version":1,"enabled":False,"maintenance_note":"Repair"})
    assert changed.status_code==200 and changed.json()["version"]==2 and not changed.json()["available"]
    assert client.patch(f"/admin/slots/{slot['id']}",headers=h,json={"version":1,"enabled":True}).status_code==409
    from app.models import Session, SlotAudit
    from sqlalchemy import select
    with Session() as db:
        audits=list(db.scalars(select(SlotAudit).where(SlotAudit.slot_id==slot["id"]).order_by(SlotAudit.id)))
        assert [a.action for a in audits]==["create","update"]
        assert audits[1].before["enabled"] is True and audits[1].after["enabled"] is False

def test_closure_allocation_race(setup):
    # Hold the exact row lock used by PATCH before allocation. SKIP LOCKED cannot
    # select this row, and after commit enabled=False must exclude it permanently.
    client,tokens=setup
    from app.models import Session, Slot, Booking
    from sqlalchemy import select
    with Session.begin() as db:
        for slot in db.scalars(select(Slot).where(Slot.id!=1)):
            slot.enabled=False
    with Session.begin() as db:
        slot=db.scalar(select(Slot).where(Slot.id==1).with_for_update())
        slot.enabled=False
        with ThreadPoolExecutor(max_workers=1) as pool:
            response=pool.submit(lambda: client.post("/allocate",headers=headers(tokens[0]),json={"vehicle":"CAR1","request_key":"closure-race"})).result(timeout=10)
        assert response.status_code==409
    assert client.post("/allocate",headers=headers(tokens[0]),json={"vehicle":"CAR1","request_key":"after-close"}).status_code==409
    # Reopen, allocate, then close an occupied slot: checkout still succeeds.
    h=admin_headers(client)
    reopened=client.patch("/admin/slots/1",headers=h,json={"version":1,"enabled":True})
    assert reopened.status_code==200
    booking=client.post("/allocate",headers=headers(tokens[0]),json={"vehicle":"CAR1","request_key":"after-reopen"}).json()
    closed=client.patch("/admin/slots/1",headers=h,json={"version":2,"enabled":False})
    assert closed.status_code==200 and closed.json()["occupied"] and not closed.json()["available"]
    assert client.post(f"/bookings/{booking['id']}/checkout",headers=headers(tokens[0])).json()["amount_cents"]==2000

def test_qr_lifecycle_replay_ownership_and_hashing(setup):
    client,tokens=setup
    h=headers(tokens[0]); ah=admin_headers(client)
    booking=client.post("/allocate",headers=h,json={"vehicle":"CAR1","request_key":"ticket-booking"}).json()
    url=f"/bookings/{booking['id']}/ticket"
    assert client.post(url,headers=headers(tokens[1])).status_code==403
    assert client.get(url,headers=h).status_code==405
    first=client.post(url,headers=h)
    assert first.status_code==200
    issued=first.json(); value=issued["token"]
    assert len(value)==43 and issued["booking"]["slot_label"]=="P-1"
    from app.models import Session, BookingTicket, Booking
    from app.main import digest_ticket
    from sqlalchemy import select
    with Session() as db:
        ticket=db.scalar(select(BookingTicket))
        assert ticket.token_hash==digest_ticket(value) and value!=ticket.token_hash
    for endpoint in ("preview","checkout"):
        assert client.post(f"/admin/tickets/{endpoint}",headers=h,json={"token":value}).status_code==403
    preview=client.post("/admin/tickets/preview",headers=ah,json={"token":value})
    assert preview.status_code==200 and preview.json()["ended_at"] is None
    with Session() as db:
        assert db.get(Booking,booking["id"]).ended_at is None
    assert client.post("/admin/tickets/preview",headers=ah,json={"token":"A"*43}).status_code==404
    assert client.post("/admin/tickets/preview",headers=ah,json={"token":"not-a-ticket"}).status_code==422
    rotated=client.post(url,headers=ah).json()["token"]
    assert rotated!=value
    assert client.post("/admin/tickets/checkout",headers=ah,json={"token":value}).status_code==404
    one=client.post("/admin/tickets/checkout",headers=ah,json={"token":rotated})
    two=client.post("/admin/tickets/checkout",headers=ah,json={"token":rotated})
    assert one.status_code==two.status_code==200
    assert one.json()==two.json() and one.json()["amount_cents"]==2000
    assert client.post(f"/bookings/{booking['id']}/checkout",headers=h).json()==one.json()
    assert client.post("/allocate",headers=h,json={"vehicle":"CAR2","request_key":"new-after-ticket"}).status_code==200
    assert client.post("/admin/tickets/checkout",headers=ah,json={"token":rotated}).json()==one.json()


def test_additive_migration_preserves_existing_bookings():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.models import Base, engine
    def load(filename):
        path=Path(__file__).parents[1]/"migrations"/"versions"/filename
        spec=importlib.util.spec_from_file_location(filename.replace(".","_"),path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    Base.metadata.drop_all(engine)
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                load("001_initial.py").upgrade()
                connection.execute(text("INSERT INTO users (id,username,password_hash,role) VALUES (1,'legacy','unused','user')"))
                connection.execute(text("INSERT INTO bookings (user_id,slot_id,vehicle,request_key) VALUES (1,1,'OLD-CAR','legacy-key')"))
                load("002_slot_management_tickets.py").upgrade()
            rows=connection.execute(text('SELECT zone,"row","column",enabled,maintenance_note,version FROM slots ORDER BY id')).all()
            assert len(rows)==12
            assert tuple(rows[0])==("A",1,1,True,"",1)
            assert tuple(rows[-1])==("A",3,4,True,"",1)
            assert connection.scalar(text("SELECT count(*) FROM bookings WHERE vehicle='OLD-CAR' AND ended_at IS NULL"))==1
            connection.execute(text('INSERT INTO slots (label,zone,"row","column") VALUES (:label,:zone,1,1)'), {"label":"NEW","zone":"B"})
            assert connection.scalar(text("SELECT max(id) FROM slots"))==13
    finally:
        Base.metadata.drop_all(engine)
