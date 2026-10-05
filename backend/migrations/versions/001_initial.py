"""Initial schema, partial unique indexes, 12 slots."""
from alembic import op
from app.models import Base, Slot
revision = "001"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    Base.metadata.create_all(op.get_bind())
    op.bulk_insert(Slot.__table__, [{"id":i,"label":f"P-{i:02d}"} for i in range(1,13)])
def downgrade(): Base.metadata.drop_all(op.get_bind())
