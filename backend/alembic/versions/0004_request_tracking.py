"""Request logs and agent-run timing.

Revision ID: 0004_request_tracking
Revises: 0003_invoice_numbers
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_request_tracking"
down_revision = "0003_invoice_numbers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("provider", sa.String(length=40), nullable=True))
    op.add_column("agent_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.create_table(
        "request_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("method", sa.String(length=12), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_request_logs_created", "request_logs", ["created_at"])
    op.create_index("ix_request_logs_path", "request_logs", ["path", "status_code"])


def downgrade() -> None:
    op.drop_index("ix_request_logs_path", table_name="request_logs")
    op.drop_index("ix_request_logs_created", table_name="request_logs")
    op.drop_table("request_logs")
    op.drop_column("agent_runs", "duration_ms")
    op.drop_column("agent_runs", "provider")
