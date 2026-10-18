"""Document expiry reminder rows.

Revision ID: 0006_document_expiry
Revises: 0005_cargo_files
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_document_expiry"
down_revision = "0005_cargo_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_expiries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("sl_no", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document_type", sa.Text(), nullable=True),
        sa.Column("document_no", sa.Text(), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("holder_name", sa.Text(), nullable=True),
        sa.Column("plate_no", sa.Text(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_document_expiries_category", "document_expiries", ["category"])
    op.create_index("ix_document_expiries_expiry", "document_expiries", ["expiry_date"])


def downgrade() -> None:
    op.drop_index("ix_document_expiries_expiry", table_name="document_expiries")
    op.drop_index("ix_document_expiries_category", table_name="document_expiries")
    op.drop_table("document_expiries")
