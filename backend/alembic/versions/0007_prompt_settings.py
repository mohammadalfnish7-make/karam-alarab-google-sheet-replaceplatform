"""Prompt versioning and app settings.

Revision ID: 0007_prompt_settings
Revises: 0006_document_expiry
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_prompt_settings"
down_revision = "0006_document_expiry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_keys",
        sa.Column("key", sa.String(length=40), primary_key=True),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("active_version_id", sa.Integer(), nullable=True),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prompt_key", sa.String(length=40), sa.ForeignKey("prompt_keys.key"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_prompt_versions_key_version", "prompt_versions", ["prompt_key", "version"], unique=True)
    op.create_index("ix_prompt_versions_key", "prompt_versions", ["prompt_key"])
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=40), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index("ix_prompt_versions_key", table_name="prompt_versions")
    op.drop_index("uq_prompt_versions_key_version", table_name="prompt_versions")
    op.drop_table("prompt_versions")
    op.drop_table("prompt_keys")
