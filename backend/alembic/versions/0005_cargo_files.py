"""Cargo evidence files linked to sea/air shipments.

Revision ID: 0005_cargo_files
Revises: 0004_request_tracking
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_cargo_files"
down_revision = "0004_request_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cargo_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("mime", sa.String(length=80), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("extracted_json", sa.JSON(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cargo_files_entity", "cargo_files", ["entity_type", "entity_id"])
    op.create_index("ix_cargo_files_sha", "cargo_files", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_cargo_files_sha", table_name="cargo_files")
    op.drop_index("ix_cargo_files_entity", table_name="cargo_files")
    op.drop_table("cargo_files")
