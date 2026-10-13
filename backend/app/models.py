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
