"""No database connections: validation, serialization, billing, SQL, throttling."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, exists
from sqlalchemy.dialects import postgresql
from app.main import SlotCreate, SlotPatch, TicketInput, serialize_slot, finish_checkout, digest_ticket, ticket_rate_limit, _ticket_attempts
from app.models import Slot, Booking

def test_slot_validation():
    assert SlotCreate(label="B-1",row=2,column=3).zone=="A"
    for body in ({"enabled":False}, {"version":1,"row":0}, {"version":1,"enabled":None}, {"version":1,"unknown":True}):
        with pytest.raises(ValidationError): SlotPatch(**body)
    assert SlotPatch(version=1,enabled=False).model_dump(exclude_unset=True)=={"version":1,"enabled":False}

def test_availability():
    slot=SimpleNamespace(id=1,label="P-1",zone="A",row=1,column=1,enabled=False,maintenance_note="Repair",version=1)
    assert not serialize_slot(slot)["available"]
    slot.enabled=True
    assert serialize_slot(slot)["available"]
    assert not serialize_slot(slot,True)["available"]

def test_ticket_validation_and_hash():
    import secrets
    value=secrets.token_urlsafe(32)
    assert TicketInput(token=value).token==value
    assert len(digest_ticket(value))==64 and digest_ticket(value)!=value
    for invalid in ("x", "x"*44, "."*43):
        with pytest.raises(ValidationError): TicketInput(token=invalid)

def test_billing_rounding_and_replay():
    now=datetime.now(timezone.utc)
    b=SimpleNamespace(id=1,slot_id=1,slot=SimpleNamespace(label="P-1"),vehicle="CAR",started_at=now-timedelta(hours=1,seconds=1),ended_at=None,amount_cents=None)
    one=finish_checkout(b)
    assert one["amount_cents"]==4000
    assert finish_checkout(b)==one

def test_allocator_sql_filters_and_locks():
    busy=exists(select(Booking.id).where(Booking.slot_id==Slot.id,Booking.ended_at.is_(None)))
    sql=str(select(Slot).where(Slot.enabled.is_(True),~busy).with_for_update(skip_locked=True).compile(dialect=postgresql.dialect()))
    assert "slots.enabled IS true" in sql and "FOR UPDATE SKIP LOCKED" in sql

def test_ticket_throttle():
    _ticket_attempts.clear()
    user=SimpleNamespace(id=999999)
    try:
        for _ in range(60): ticket_rate_limit(user)
        with pytest.raises(HTTPException) as error: ticket_rate_limit(user)
        assert error.value.status_code==429
    finally:
        _ticket_attempts.clear()


def test_migrations_compile_for_postgresql_offline():
    import importlib.util
    import io
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    output=io.StringIO()
    context=MigrationContext.configure(dialect_name="postgresql",opts={"as_sql":True,"output_buffer":output})
    with Operations.context(context):
        for name in ("001_initial.py","002_slot_management_tickets.py"):
            path=Path(__file__).parents[1]/"migrations"/"versions"/name
            spec=importlib.util.spec_from_file_location("migration_"+name.replace(".","_"),path)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.upgrade()
    sql=output.getvalue()
    assert sql.count("CREATE TABLE slots (")==1
    assert 'ADD COLUMN row INTEGER DEFAULT' in sql or 'ADD COLUMN "row" INTEGER DEFAULT' in sql
    assert "CREATE TABLE slot_audit" in sql and "CREATE TABLE booking_tickets" in sql
    assert "uq_active_slot" in sql and "uq_slot_position" in sql


def test_deployment_version_and_body_only_ticket_contract():
    from app.main import app, APP_VERSION
    schema=app.openapi()
    assert schema["info"]["version"]==APP_VERSION=="1.1.0"
    for path in ("/admin/tickets/preview", "/admin/tickets/checkout"):
        assert set(schema["paths"][path])=={"post"}
        operation=schema["paths"][path]["post"]
        assert "application/json" in operation["requestBody"]["content"]
        assert not any(p["in"]=="query" for p in operation.get("parameters",[]))
    assert set(schema["paths"]["/bookings/{booking_id}/ticket"])=={"post"}
