import os
from datetime import datetime
from sqlalchemy import create_engine, String, ForeignKey, DateTime, Integer, Index, text, CheckConstraint, Boolean, UniqueConstraint, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(10), default="user")
class Slot(Base):
    __tablename__ = "slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(20), unique=True)
    zone: Mapped[str] = mapped_column(String(20), default="A", server_default="A")
    row: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    column: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    maintenance_note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    __table_args__ = (
        UniqueConstraint("zone", "row", "column", name="uq_slot_position"),
        CheckConstraint('"row" > 0 AND "column" > 0', name="ck_slot_position"),
        CheckConstraint("version > 0", name="ck_slot_version"),
    )
class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    vehicle: Mapped[str] = mapped_column(String(20))
    request_key: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slot: Mapped[Slot] = relationship(lazy="selectin")
    __table_args__ = (
        Index("uq_active_slot", "slot_id", unique=True, postgresql_where=text("ended_at IS NULL")),
        Index("uq_active_user", "user_id", unique=True, postgresql_where=text("ended_at IS NULL")),
        Index("uq_request", "user_id", "request_key", unique=True),
        CheckConstraint("amount_cents IS NULL OR amount_cents >= 0"),
    )
class SlotAudit(Base):
    __tablename__ = "slot_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(20))
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
class BookingTicket(Base):
    __tablename__ = "booking_tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)
