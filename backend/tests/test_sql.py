from sqlalchemy import select, exists
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex
from app.models import Slot, Booking

def test_locking_sql():
    busy = exists(select(Booking.id).where(Booking.slot_id == Slot.id, Booking.ended_at.is_(None)))
    query = select(Slot).where(~busy).order_by(Slot.id).with_for_update(skip_locked=True).limit(1)
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "NOT (EXISTS" in sql

def test_database_constraints():
    indexes = {i.name: str(CreateIndex(i).compile(dialect=postgresql.dialect())) for i in Booking.__table__.indexes}
    assert "UNIQUE INDEX" in indexes["uq_active_slot"]
    assert "WHERE ended_at IS NULL" in indexes["uq_active_slot"]
    assert "WHERE ended_at IS NULL" in indexes["uq_active_user"]
    assert "UNIQUE INDEX" in indexes["uq_request"]
