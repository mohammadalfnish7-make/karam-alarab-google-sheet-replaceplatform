"""Standalone container loading rows (mark + container_no).

Revision ID: 0011_container_loading
Revises: 0010_cargo_file_soft_delete
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_container_loading"
down_revision = "0010_cargo_file_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "container_loadings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mark", sa.Text(), nullable=False),
        sa.Column("container_no", sa.Text(), nullable=True),
        sa.Column("container_row_id", sa.Integer(), sa.ForeignKey("container_rows.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_container_loadings_mark", "container_loadings", ["mark"], unique=True)
    op.create_index("ix_container_loadings_container_no", "container_loadings", ["container_no"])
    op.create_index("ix_container_loadings_container_row", "container_loadings", ["container_row_id"])


def downgrade() -> None:
    op.drop_index("ix_container_loadings_container_row", table_name="container_loadings")
    op.drop_index("ix_container_loadings_container_no", table_name="container_loadings")
    op.drop_index("ix_container_loadings_mark", table_name="container_loadings")
    op.drop_table("container_loadings")
