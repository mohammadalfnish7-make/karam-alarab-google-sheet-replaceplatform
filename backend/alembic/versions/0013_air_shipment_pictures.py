"""Standalone air shipment pictures table.

Revision ID: 0013_air_shipment_pictures
Revises: 0012_expenses
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_air_shipment_pictures"
down_revision = "0012_expenses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "air_shipment_pictures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("cartons", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_air_shipment_pictures_number", "air_shipment_pictures", ["number"], unique=True)
    op.create_index("ix_air_shipment_pictures_date", "air_shipment_pictures", ["date"])


def downgrade() -> None:
    op.drop_index("ix_air_shipment_pictures_date", table_name="air_shipment_pictures")
    op.drop_index("ix_air_shipment_pictures_number", table_name="air_shipment_pictures")
    op.drop_table("air_shipment_pictures")
