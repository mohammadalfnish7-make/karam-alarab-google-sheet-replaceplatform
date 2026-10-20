"""Add visible stage column on Cont Tracker rows.

Revision ID: 0009_container_stage
Revises: 0008_container_tracker
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_container_stage"
down_revision = "0008_container_tracker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("container_rows", sa.Column("stage", sa.Text(), nullable=True))
    # Backfill from undocumented sheet column stored at extra_json key "16"
    op.execute(
        """
        UPDATE container_rows
        SET stage = extra_json->>'16'
        WHERE stage IS NULL
          AND extra_json IS NOT NULL
          AND extra_json ? '16'
          AND coalesce(extra_json->>'16', '') <> ''
        """
    )


def downgrade() -> None:
    op.drop_column("container_rows", "stage")
