"""Initial schema, partial unique indexes, 12 slots (frozen historical schema)."""
from alembic import op
import sqlalchemy as sa
revision = "001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer, primary_key=True), sa.Column("username", sa.String(50), nullable=False, unique=True), sa.Column("password_hash", sa.String(300), nullable=False), sa.Column("role", sa.String(10), nullable=False))
    slots = op.create_table("slots", sa.Column("id", sa.Integer, primary_key=True), sa.Column("label", sa.String(20), nullable=False, unique=True))
    op.create_table("bookings", sa.Column("id", sa.Integer, primary_key=True), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False), sa.Column("slot_id", sa.Integer, sa.ForeignKey("slots.id"), nullable=False), sa.Column("vehicle", sa.String(20), nullable=False), sa.Column("request_key", sa.String(80), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("ended_at", sa.DateTime(timezone=True)), sa.Column("amount_cents", sa.Integer), sa.CheckConstraint("amount_cents IS NULL OR amount_cents >= 0"))
    op.create_index("uq_active_slot", "bookings", ["slot_id"], unique=True, postgresql_where=sa.text("ended_at IS NULL"))
    op.create_index("uq_active_user", "bookings", ["user_id"], unique=True, postgresql_where=sa.text("ended_at IS NULL"))
    op.create_index("uq_request", "bookings", ["user_id", "request_key"], unique=True)
    op.bulk_insert(slots, [{"id":i,"label":f"P-{i:02d}"} for i in range(1,13)])
    # Explicit seed IDs must advance the PostgreSQL sequence for subsequent admin inserts.
    op.execute("SELECT setval(pg_get_serial_sequence('slots','id'), (SELECT MAX(id) FROM slots))")

def downgrade():
    op.drop_table("bookings")
    op.drop_table("slots")
    op.drop_table("users")
