"""Standalone Qusai expenses table.

Revision ID: 0012_expenses
Revises: 0011_container_loading
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_expenses"
down_revision = "0011_container_loading"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mark", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 3), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="AED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_expenses_mark", "expenses", ["mark"], unique=True)
    op.create_index("ix_expenses_date", "expenses", ["date"])


def downgrade() -> None:
    op.drop_index("ix_expenses_date", table_name="expenses")
    op.drop_index("ix_expenses_mark", table_name="expenses")
    op.drop_table("expenses")
