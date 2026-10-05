"""Destructive integration tests: ONLY point TEST_DATABASE_URL at a disposable database."""
import os
import pytest
from concurrent.futures import ThreadPoolExecutor

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL database not configured")
@pytest.fixture()
def setup():
    url = os.environ["TEST_DATABASE_URL"]
    if not url.startswith("postgresql"): pytest.fail("Integration tests require real PostgreSQL")
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("JWT_SECRET", "test-only-secret-" + "x" * 40)
    from app.models import Base, engine, Session, Slot, User
    from app.security import hash_password
    from app.main import app
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session.begin() as db:
        db.add_all([Slot(id=i,label=f"P-{i}") for i in range(1,4)])
        db.add_all([User(username=f"user{i}",password_hash=hash_password("password-for-tests"),role="user") for i in range(12)])
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
