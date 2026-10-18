"""Store every invoice number on an exit row."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_invoice_numbers"
down_revision = "0002_agent_runs"
branch_labels = None
depends_on = None

jsonb = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("exit_records", sa.Column("invoice_numbers", jsonb, nullable=True))


def downgrade() -> None:
    op.drop_column("exit_records", "invoice_numbers")
