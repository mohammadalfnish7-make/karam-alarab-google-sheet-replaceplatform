"""Standalone image invoices from product photos.

Revision ID: 0017_image_invoices
Revises: 0016_loading_invoices
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_image_invoices"
down_revision = "0016_loading_invoices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_table(
        "image_invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("image_invoice_id", sa.Integer(), sa.ForeignKey("image_invoices.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brand_name", sa.Text(), nullable=True),
        sa.Column("barcode", sa.Text(), nullable=True),
        sa.Column("made_in", sa.Text(), nullable=True),
        sa.Column("volume", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_image_invoice_lines_invoice_id", "image_invoice_lines", ["image_invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_image_invoice_lines_invoice_id", table_name="image_invoice_lines")
    op.drop_table("image_invoice_lines")
    op.drop_table("image_invoices")
