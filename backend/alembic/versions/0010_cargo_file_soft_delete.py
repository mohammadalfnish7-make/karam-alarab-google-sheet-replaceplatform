"""Soft-delete columns on cargo_files for container loading MVP.

Revision ID: 0010_cargo_file_soft_delete
Revises: 0009_container_stage
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_cargo_file_soft_delete"
down_revision = "0009_container_stage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cargo_files", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "cargo_files",
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cargo_files", "deleted_by")
    op.drop_column("cargo_files", "deleted_at")
