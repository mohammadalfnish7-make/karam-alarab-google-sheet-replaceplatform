from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database import Base


def json_type():
    return JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("uq_customer_code_lower", func.lower(Customer.code), unique=True)
Index("uq_company_name_lower", func.lower(Company.name), unique=True)
Index("uq_supplier_name_lower", func.lower(Supplier.name), unique=True)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    sea_count: Mapped[int] = mapped_column(Integer, nullable=False)
    air_count: Mapped[int] = mapped_column(Integer, nullable=False)
    exit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    before_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    after_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    changed_fields: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_audit_created", AuditLog.created_at)
Index("ix_audit_entity", AuditLog.entity_type, AuditLog.entity_id)
Index("ix_audit_actor", AuditLog.actor_user_id)


class SeaCargo(Base):
    __tablename__ = "sea_cargo"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issues: Mapped[Any] = mapped_column(json_type(), nullable=False, default=list)
    date_received: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    customer_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cartons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_weight_kg: Mapped[Any | None] = mapped_column(Numeric(14, 3), nullable=True)
    gross_is_no_pallet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    net_weight_kg: Mapped[Any | None] = mapped_column(Numeric(14, 3), nullable=True)
    system_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipment_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_route: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AirCargo(Base):
    __tablename__ = "air_cargo"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issues: Mapped[Any] = mapped_column(json_type(), nullable=False, default=list)
    date_received: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    customer_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cartons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_weight_kg: Mapped[Any | None] = mapped_column(Numeric(14, 3), nullable=True)
    gross_is_no_pallet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    net_weight_kg: Mapped[Any | None] = mapped_column(Numeric(14, 3), nullable=True)
    system_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipment_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ExitRecord(Base):
    __tablename__ = "exit_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issues: Mapped[Any] = mapped_column(json_type(), nullable=False, default=list)
    no: Mapped[int] = mapped_column(Integer, nullable=False)
    mark: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_numbers: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    cartons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_of_submission: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


Index("ix_sea_system_code", SeaCargo.system_code)
Index("ix_air_system_code", AirCargo.system_code)
Index(
    "uq_exit_no_active",
    ExitRecord.no,
    unique=True,
    sqlite_where=text("deleted_at IS NULL"),
    postgresql_where=text("deleted_at IS NULL"),
)


class DocumentExpiry(Base):
    """Company / employee / vehicle document expiry for reminders."""

    __tablename__ = "document_expiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)  # company | employee | vehicle
    sl_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    holder_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    plate_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index("ix_document_expiries_category", DocumentExpiry.category)
Index("ix_document_expiries_expiry", DocumentExpiry.expiry_date)


class CargoFile(Base):
    """Evidence file linked to a cargo or container row (note | scale | loading)."""

    __tablename__ = "cargo_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # note | scale | loading
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(String(80), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


Index("ix_cargo_files_entity", CargoFile.entity_type, CargoFile.entity_id)
Index("ix_cargo_files_sha", CargoFile.sha256)


class PdfDocument(Base):
    __tablename__ = "pdf_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(16), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_row_ids: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class PdfExtraction(Base):
    __tablename__ = "pdf_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"), nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    steps_json: Mapped[Any] = mapped_column(json_type(), nullable=False, default=list)
    output_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_agent_runs_started", AgentRun.started_at)
Index("ix_agent_runs_agent", AgentRun.agent_name, AgentRun.status)
Index("ix_request_logs_created", RequestLog.created_at)
Index("ix_request_logs_path", RequestLog.path, RequestLog.status_code)


class PromptKey(Base):
    __tablename__ = "prompt_keys"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    active_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_key: Mapped[str] = mapped_column(ForeignKey("prompt_keys.key"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("uq_prompt_versions_key_version", PromptVersion.prompt_key, PromptVersion.version, unique=True)
Index("ix_prompt_versions_key", PromptVersion.prompt_key)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ContainerRow(Base):
    """Cont Tracker sheet row."""

    __tablename__ = "container_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issues: Mapped[Any] = mapped_column(json_type(), nullable=False, default=list)
    date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    inv_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_cont: Mapped[str | None] = mapped_column(Text, nullable=True)
    container_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    kgs: Mapped[Any | None] = mapped_column(Numeric(14, 3), nullable=True)
    carton: Mapped[int | None] = mapped_column(Integer, nullable=True)
    driver_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    driver_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    info: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    foreign_invoice: Mapped[str | None] = mapped_column(Text, nullable=True)
    russian_instrct: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_buyer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AirShipmentTrackerRow(Base):
    """Air Shipment Tracker sheet row."""

    __tablename__ = "air_shipment_tracker_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issues: Mapped[Any] = mapped_column(json_type(), nullable=False, default=list)
    ref_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor: Mapped[str | None] = mapped_column(Text, nullable=True)
    airline: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    item: Mapped[str | None] = mapped_column(Text, nullable=True)
    cartons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Any | None] = mapped_column(Numeric(14, 3), nullable=True)
    awb: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class CooRow(Base):
    """COO sheet row."""

    __tablename__ = "coo_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issues: Mapped[Any] = mapped_column(json_type(), nullable=False, default=list)
    sr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inv_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    container_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    kjs: Mapped[str | None] = mapped_column(Text, nullable=True)
    grg: Mapped[str | None] = mapped_column(Text, nullable=True)
    k_exit: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class FlightScheduleRow(Base):
    """Flight Schedule sheet row."""

    __tablename__ = "flight_schedule_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issues: Mapped[Any] = mapped_column(json_type(), nullable=False, default=list)
    sr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    airline: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    day: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrow: Mapped[str | None] = mapped_column(Text, nullable=True)
    wide: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    column_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ContainerLoading(Base):
    """Standalone container loading record (mark + container number + photos)."""

    __tablename__ = "container_loadings"

    id: Mapped[int] = mapped_column(primary_key=True)
    mark: Mapped[str] = mapped_column(Text, nullable=False)
    container_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    container_row_id: Mapped[int | None] = mapped_column(ForeignKey("container_rows.id"), nullable=True)
    plan_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    plan_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    summary_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class LoadingInvoice(Base):
    """Invoice / packing list linked to a container loading plan."""

    __tablename__ = "loading_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(Text, nullable=False)
    container_loading_id: Mapped[int | None] = mapped_column(
        ForeignKey("container_loadings.id"), nullable=True
    )
    container_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Expense(Base):
    """Standalone Qusai expense (amount + currency + notes + receipt photos)."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    mark: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    amount: Mapped[Any | None] = mapped_column(Numeric(14, 3), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="AED")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[Any | None] = mapped_column(json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AirShipmentPicture(Base):
    """Standalone air shipment photo record (AR number + cartons + photos)."""

    __tablename__ = "air_shipment_pictures"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    cartons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ImageInvoice(Base):
    """Session for building invoice lines from product photos (hand + AI)."""

    __tablename__ = "image_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ImageInvoiceLine(Base):
    """One product row on an image invoice; photos live in cargo_files."""

    __tablename__ = "image_invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_invoice_id: Mapped[int] = mapped_column(ForeignKey("image_invoices.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    brand_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    barcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    made_in: Mapped[str | None] = mapped_column(Text, nullable=True)
    volume: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Any | None] = mapped_column(Numeric(14, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index("ix_container_rows_inv", ContainerRow.inv_no)
Index("ix_air_tracker_ref", AirShipmentTrackerRow.ref_no)
Index("ix_coo_inv", CooRow.inv_number)
Index(
    "ix_container_loadings_mark",
    ContainerLoading.mark,
    unique=True,
    sqlite_where=text("deleted_at IS NULL"),
    postgresql_where=text("deleted_at IS NULL"),
)
Index("ix_container_loadings_container_no", ContainerLoading.container_no)
Index("ix_container_loadings_container_row", ContainerLoading.container_row_id)
Index(
    "ix_expenses_mark",
    Expense.mark,
    unique=True,
    sqlite_where=text("deleted_at IS NULL"),
    postgresql_where=text("deleted_at IS NULL"),
)
Index("ix_expenses_date", Expense.date)
Index(
    "ix_air_shipment_pictures_number",
    AirShipmentPicture.number,
    unique=True,
    sqlite_where=text("deleted_at IS NULL"),
    postgresql_where=text("deleted_at IS NULL"),
)
Index("ix_air_shipment_pictures_date", AirShipmentPicture.date)
Index("ix_image_invoice_lines_invoice_id", ImageInvoiceLine.image_invoice_id)
