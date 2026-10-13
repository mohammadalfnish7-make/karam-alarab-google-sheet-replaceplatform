"""Initial schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

jsonb = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_customer_code_lower", "customers", [sa.text("lower(code)")], unique=True)
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_company_name_lower", "companies", [sa.text("lower(name)")], unique=True)
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_supplier_name_lower", "suppliers", [sa.text("lower(name)")], unique=True)
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("sea_count", sa.Integer(), nullable=False),
        sa.Column("air_count", sa.Integer(), nullable=False),
        sa.Column("exit_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("filename"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=True),
        sa.Column("entity_id", sa.String(length=40), nullable=True),
        sa.Column("before_json", jsonb, nullable=True),
        sa.Column("after_json", jsonb, nullable=True),
        sa.Column("changed_fields", jsonb, nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_created", "audit_log", ["created_at"])
    op.create_index("ix_audit_entity", "audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_audit_actor", "audit_log", ["actor_user_id"])

    def cargo_columns(extra):
        return [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("issues", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("date_received", sa.Date(), nullable=True),
            sa.Column("customer_code", sa.Text(), nullable=True),
            sa.Column("company_name", sa.Text(), nullable=True),
            sa.Column("cartons", sa.Integer(), nullable=True),
            sa.Column("gross_weight_kg", sa.Numeric(14, 3), nullable=True),
            sa.Column("gross_is_no_pallet", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("net_weight_kg", sa.Numeric(14, 3), nullable=True),
            sa.Column("system_code", sa.Text(), nullable=True),
            sa.Column("shipment_number", sa.Text(), nullable=True),
            *extra,
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        ]

    op.create_table(
        "sea_cargo",
        *cargo_columns(
            [
                sa.Column("shipping_route", sa.Text(), nullable=True),
                sa.Column("stage", sa.Text(), nullable=True),
            ]
        ),
    )
    op.create_index("ix_sea_system_code", "sea_cargo", ["system_code"])
    op.create_table(
        "air_cargo",
        *cargo_columns([sa.Column("status", sa.Text(), nullable=True)]),
    )
    op.create_index("ix_air_system_code", "air_cargo", ["system_code"])
    op.create_table(
        "exit_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("issues", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("no", sa.Integer(), nullable=False),
        sa.Column("mark", sa.Text(), nullable=True),
        sa.Column("supplier", sa.Text(), nullable=True),
        sa.Column("invoice_no", sa.Text(), nullable=True),
        sa.Column("cartons", sa.Integer(), nullable=True),
        sa.Column("date_of_submission", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "uq_exit_no_active",
        "exit_records",
        ["no"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "pdf_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target", sa.String(length=16), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_row_ids", jsonb, nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_table(
        "pdf_extractions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("pdf_documents.id"), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("parsed_json", jsonb, nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pdf_extractions")
    op.drop_table("pdf_documents")
    op.drop_index("uq_exit_no_active", table_name="exit_records")
    op.drop_table("exit_records")
    op.drop_index("ix_air_system_code", table_name="air_cargo")
    op.drop_table("air_cargo")
    op.drop_index("ix_sea_system_code", table_name="sea_cargo")
    op.drop_table("sea_cargo")
    op.drop_index("ix_audit_actor", table_name="audit_log")
    op.drop_index("ix_audit_entity", table_name="audit_log")
    op.drop_index("ix_audit_created", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("import_batches")
    op.drop_index("uq_supplier_name_lower", table_name="suppliers")
    op.drop_table("suppliers")
    op.drop_index("uq_company_name_lower", table_name="companies")
    op.drop_table("companies")
    op.drop_index("uq_customer_code_lower", table_name="customers")
    op.drop_table("customers")
    op.drop_table("users")
