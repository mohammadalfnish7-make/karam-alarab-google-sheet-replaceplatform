"""Container tracker sheets (Cont, Air tracker, COO, Flight schedule).

Revision ID: 0008_container_tracker
Revises: 0007_prompt_settings
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_container_tracker"
down_revision = "0007_prompt_settings"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    ]


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("container_rows"):
        op.create_table(
            "container_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("issues", _json(), nullable=False),
            sa.Column("date", sa.Date(), nullable=True),
            sa.Column("inv_no", sa.Text(), nullable=True),
            sa.Column("qr", sa.Text(), nullable=True),
            sa.Column("previous_cont", sa.Text(), nullable=True),
            sa.Column("container_no", sa.Text(), nullable=True),
            sa.Column("kgs", sa.Numeric(14, 3), nullable=True),
            sa.Column("carton", sa.Integer(), nullable=True),
            sa.Column("driver_name", sa.Text(), nullable=True),
            sa.Column("driver_contact", sa.Text(), nullable=True),
            sa.Column("info", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("foreign_invoice", sa.Text(), nullable=True),
            sa.Column("russian_instrct", sa.Text(), nullable=True),
            sa.Column("supplier_buyer", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=True),
            sa.Column("extra_json", _json(), nullable=True),
            *_audit_columns(),
        )
        op.create_index("ix_container_rows_inv", "container_rows", ["inv_no"])

    if not _has_table("air_shipment_tracker_rows"):
        op.create_table(
            "air_shipment_tracker_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("issues", _json(), nullable=False),
            sa.Column("ref_no", sa.Text(), nullable=True),
            sa.Column("vendor", sa.Text(), nullable=True),
            sa.Column("airline", sa.Text(), nullable=True),
            sa.Column("date", sa.Date(), nullable=True),
            sa.Column("item", sa.Text(), nullable=True),
            sa.Column("cartons", sa.Integer(), nullable=True),
            sa.Column("weight_kg", sa.Numeric(14, 3), nullable=True),
            sa.Column("awb", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("extra_json", _json(), nullable=True),
            *_audit_columns(),
        )
        op.create_index("ix_air_tracker_ref", "air_shipment_tracker_rows", ["ref_no"])

    if not _has_table("coo_rows"):
        op.create_table(
            "coo_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("issues", _json(), nullable=False),
            sa.Column("sr", sa.Integer(), nullable=True),
            sa.Column("inv_number", sa.Text(), nullable=True),
            sa.Column("container_no", sa.Text(), nullable=True),
            sa.Column("kjs", sa.Text(), nullable=True),
            sa.Column("grg", sa.Text(), nullable=True),
            sa.Column("k_exit", sa.Text(), nullable=True),
            sa.Column("extra_json", _json(), nullable=True),
            *_audit_columns(),
        )
        op.create_index("ix_coo_inv", "coo_rows", ["inv_number"])

    if not _has_table("flight_schedule_rows"):
        op.create_table(
            "flight_schedule_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("issues", _json(), nullable=False),
            sa.Column("sr", sa.Integer(), nullable=True),
            sa.Column("airline", sa.Text(), nullable=True),
            sa.Column("date", sa.Date(), nullable=True),
            sa.Column("day", sa.Text(), nullable=True),
            sa.Column("narrow", sa.Text(), nullable=True),
            sa.Column("wide", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=True),
            sa.Column("column_1", sa.Text(), nullable=True),
            sa.Column("extra_json", _json(), nullable=True),
            *_audit_columns(),
        )


def downgrade() -> None:
    op.drop_table("flight_schedule_rows")
    op.drop_index("ix_coo_inv", table_name="coo_rows")
    op.drop_table("coo_rows")
    op.drop_index("ix_air_tracker_ref", table_name="air_shipment_tracker_rows")
    op.drop_table("air_shipment_tracker_rows")
    op.drop_index("ix_container_rows_inv", table_name="container_rows")
    op.drop_table("container_rows")
