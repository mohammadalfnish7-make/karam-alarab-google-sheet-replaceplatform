"""Agent run registry."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_agent_runs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

jsonb = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity_type", sa.String(length=40), nullable=True),
        sa.Column("entity_id", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("input_json", jsonb, nullable=True),
        sa.Column("steps_json", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("output_json", jsonb, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_stack", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_started", "agent_runs", ["started_at"])
    op.create_index("ix_agent_runs_agent", "agent_runs", ["agent_name", "status"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_agent", table_name="agent_runs")
    op.drop_index("ix_agent_runs_started", table_name="agent_runs")
    op.drop_table("agent_runs")
