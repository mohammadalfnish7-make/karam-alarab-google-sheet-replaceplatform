"""Container loading plan_json + check_json (standalone).

Revision ID: 0015_loading_plan_check
Revises: 0014_soft_delete_mark_unique
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_loading_plan_check"
down_revision = "0014_soft_delete_mark_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("container_loadings", sa.Column("plan_json", sa.JSON(), nullable=True))
    op.add_column("container_loadings", sa.Column("plan_filename", sa.Text(), nullable=True))
    op.add_column("container_loadings", sa.Column("check_json", sa.JSON(), nullable=True))
    op.add_column("container_loadings", sa.Column("summary_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("container_loadings", "summary_json")
    op.drop_column("container_loadings", "check_json")
    op.drop_column("container_loadings", "plan_filename")
    op.drop_column("container_loadings", "plan_json")
