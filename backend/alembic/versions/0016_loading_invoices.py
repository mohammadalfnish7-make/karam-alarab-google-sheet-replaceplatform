"""Standalone loading invoices linked to container loadings.

Revision ID: 0016_loading_invoices
Revises: 0015_loading_plan_check
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_loading_invoices"
down_revision = "0015_loading_plan_check"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loading_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ref", sa.Text(), nullable=False),
        sa.Column("container_loading_id", sa.Integer(), sa.ForeignKey("container_loadings.id"), nullable=True),
        sa.Column("container_no", sa.Text(), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("invoice_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_loading_invoices_ref", "loading_invoices", ["ref"])
    op.create_index("ix_loading_invoices_loading_id", "loading_invoices", ["container_loading_id"])


def downgrade() -> None:
    op.drop_index("ix_loading_invoices_loading_id", table_name="loading_invoices")
    op.drop_index("ix_loading_invoices_ref", table_name="loading_invoices")
    op.drop_table("loading_invoices")
