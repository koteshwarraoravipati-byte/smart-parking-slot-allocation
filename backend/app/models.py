import os
from datetime import datetime
from sqlalchemy import create_engine, String, ForeignKey, DateTime, Integer, Index, text, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

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
    __table_args__ = (
        Index("uq_active_slot", "slot_id", unique=True, postgresql_where=text("ended_at IS NULL")),
        Index("uq_active_user", "user_id", unique=True, postgresql_where=text("ended_at IS NULL")),
        Index("uq_request", "user_id", "request_key", unique=True),
        CheckConstraint("amount_cents IS NULL OR amount_cents >= 0"),
    )
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)
