"""Add slot management, audit history, and hashed parking tickets."""
from alembic import op
import sqlalchemy as sa
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("slots", sa.Column("zone", sa.String(20), nullable=False, server_default="A"))
    op.add_column("slots", sa.Column("row", sa.Integer, nullable=False, server_default="1"))
    op.add_column("slots", sa.Column("column", sa.Integer, nullable=False, server_default="1"))
    op.add_column("slots", sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()))
    op.add_column("slots", sa.Column("maintenance_note", sa.String(500), nullable=False, server_default=""))
    op.add_column("slots", sa.Column("version", sa.Integer, nullable=False, server_default="1"))
    # Stable ID ordering, three rows of four for the original twelve; also handles extra existing slots.
    op.execute('WITH positions AS (SELECT id, row_number() OVER (ORDER BY id) - 1 AS n FROM slots) UPDATE slots SET "row" = (positions.n / 4)::integer + 1, "column" = (positions.n % 4)::integer + 1 FROM positions WHERE slots.id = positions.id')
    op.create_unique_constraint("uq_slot_position", "slots", ["zone", "row", "column"])
    op.create_check_constraint("ck_slot_position", "slots", '"row" > 0 AND "column" > 0')
    op.create_check_constraint("ck_slot_version", "slots", "version > 0")
    op.execute("SELECT setval(pg_get_serial_sequence('slots','id'), COALESCE((SELECT MAX(id) FROM slots), 1), EXISTS(SELECT 1 FROM slots))")
    op.create_table("slot_audit", sa.Column("id", sa.Integer, primary_key=True), sa.Column("slot_id", sa.Integer, sa.ForeignKey("slots.id"), nullable=False), sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False), sa.Column("action", sa.String(20), nullable=False), sa.Column("before", sa.JSON), sa.Column("after", sa.JSON, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_table("booking_tickets", sa.Column("id", sa.Integer, primary_key=True), sa.Column("booking_id", sa.Integer, sa.ForeignKey("bookings.id"), nullable=False, unique=True), sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

def downgrade():
    op.drop_table("booking_tickets")
    op.drop_table("slot_audit")
    op.drop_constraint("ck_slot_version", "slots")
    op.drop_constraint("ck_slot_position", "slots")
    op.drop_constraint("uq_slot_position", "slots")
    for name in ["version", "maintenance_note", "enabled", "column", "row", "zone"]:
        op.drop_column("slots", name)
