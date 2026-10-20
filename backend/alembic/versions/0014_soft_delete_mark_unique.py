"""Unique mark/number only among live (non-deleted) rows.

Revision ID: 0014_soft_delete_mark_unique
Revises: 0013_air_shipment_pictures
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_soft_delete_mark_unique"
down_revision = "0013_air_shipment_pictures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_container_loadings_mark", table_name="container_loadings")
    op.create_index(
        "ix_container_loadings_mark",
        "container_loadings",
        ["mark"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.drop_index("ix_expenses_mark", table_name="expenses")
    op.create_index(
        "ix_expenses_mark",
        "expenses",
        ["mark"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.drop_index("ix_air_shipment_pictures_number", table_name="air_shipment_pictures")
    op.create_index(
        "ix_air_shipment_pictures_number",
        "air_shipment_pictures",
        ["number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_air_shipment_pictures_number", table_name="air_shipment_pictures")
    op.create_index(
        "ix_air_shipment_pictures_number",
        "air_shipment_pictures",
        ["number"],
        unique=True,
    )

    op.drop_index("ix_expenses_mark", table_name="expenses")
    op.create_index("ix_expenses_mark", "expenses", ["mark"], unique=True)

    op.drop_index("ix_container_loadings_mark", table_name="container_loadings")
    op.create_index("ix_container_loadings_mark", "container_loadings", ["mark"], unique=True)
