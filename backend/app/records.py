from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.constants import ENTITY_TYPES
from app.errors import AppError
from app.models import AirCargo, Company, Customer, ExitRecord, SeaCargo, Supplier, User
from app.present import (
    AIR_FIELDS,
    EXIT_FIELDS,
    SEA_FIELDS,
    cargo_out,
    diff,
    exit_out,
    snapshot,
)
from app.validation import validate_cargo, validate_exit

EXIT_EDIT_FIELDS = [
    "mark",
    "supplier",
    "invoice_no",
    "cartons",
    "date_of_submission",
    "status",
]


def like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def ensure_named(db: Session, model, attr: str, value: str) -> str:
    column = getattr(model, attr)
    found = db.scalar(select(model).where(func.lower(column) == value.lower()))
    if found:
        return getattr(found, attr)
    row = model(**{attr: value, "created_at": datetime.now(timezone.utc)})
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        found = db.scalar(select(model).where(func.lower(column) == value.lower()))
        if found:
            return getattr(found, attr)
        raise
    return value


def merge_input(existing: Any | None, patch: dict, fields: list[str]) -> dict:
    if existing is None:
        return dict(patch)
    base = {name: getattr(existing, name) for name in fields}
    for key, value in patch.items():
        if key.startswith("confirm_"):
            continue
        base[key] = value
    return base


def _apply_master_inserts(db: Session, result, *, customer_field: str | None, company: bool, supplier: bool) -> None:
    if result.insert_customer and customer_field:
        result.values[customer_field] = ensure_named(db, Customer, "code", result.insert_customer)
    if company and result.insert_company:
        result.values["company_name"] = ensure_named(db, Company, "name", result.insert_company)
    if supplier and result.insert_supplier:
        result.values["supplier"] = ensure_named(db, Supplier, "name", result.insert_supplier)


def apply_cargo(db: Session, kind: str, result, user: User, request, existing=None):
    fields = SEA_FIELDS if kind == "sea" else AIR_FIELDS
    model = SeaCargo if kind == "sea" else AirCargo
    now = datetime.now(timezone.utc)
    _apply_master_inserts(db, result, customer_field="customer_code", company=True, supplier=False)
    if existing is None:
        row = model(
            legacy=False,
            needs_review=False,
            issues=[],
            created_at=now,
            created_by=user.id,
            gross_is_no_pallet=False,
        )
        before = {name: None for name in fields}
        before["deleted_at"] = None
        before["deleted_by"] = None
        action = "create"
        db.add(row)
    else:
        row = existing
        before = snapshot(row, fields)
        action = "update"
        row.updated_at = now
        row.updated_by = user.id
    for name in fields:
        setattr(row, name, result.values.get(name))
    db.flush()
    after = snapshot(row, fields)
    changed = diff(before, after, fields)
    if action == "create" or changed:
        write_audit(
            db,
            actor_user_id=user.id,
            action=action,
            entity_type=ENTITY_TYPES[kind],
            entity_id=row.id,
            before=None if action == "create" else before,
            after=after,
            changed=changed,
            request=request,
        )
    return row


def save_cargo(db: Session, kind: str, data: dict, confirms: dict, user: User, request, existing=None) -> dict:
    fields = SEA_FIELDS if kind == "sea" else AIR_FIELDS
    merged = merge_input(existing, data, fields)
    result = validate_cargo(
        db,
        kind,
        merged,
        existing,
        confirm_new_customer=bool(confirms.get("confirm_new_customer")),
        confirm_new_company=bool(confirms.get("confirm_new_company")),
    )
    if result.field_errors:
        raise AppError(422, result.payload())
    row = apply_cargo(db, kind, result, user, request, existing)
    db.commit()
    return {"item": cargo_out(row, kind), "warnings": result.warnings}


def apply_exit(db: Session, result, user: User, request, existing=None):
    now = datetime.now(timezone.utc)
    _apply_master_inserts(db, result, customer_field="mark", company=False, supplier=True)
    if existing is None:
        row = ExitRecord(
            legacy=False,
            needs_review=False,
            issues=[],
            no=next_exit_no(db),
            created_at=now,
            created_by=user.id,
        )
        before = {name: None for name in EXIT_FIELDS}
        before["deleted_at"] = None
        before["deleted_by"] = None
        action = "create"
        db.add(row)
    else:
        row = existing
        before = snapshot(row, EXIT_FIELDS)
        action = "update"
        row.updated_at = now
        row.updated_by = user.id
    for name in EXIT_EDIT_FIELDS:
        setattr(row, name, result.values.get(name))
    db.flush()
    after = snapshot(row, EXIT_FIELDS)
    changed = diff(before, after, EXIT_FIELDS)
    if action == "create" or changed:
        write_audit(
            db,
            actor_user_id=user.id,
            action=action,
            entity_type="exit_record",
            entity_id=row.id,
            before=None if action == "create" else before,
            after=after,
            changed=changed,
            request=request,
        )
    return row


def save_exit(db: Session, data: dict, confirms: dict, user: User, request, existing=None) -> dict:
    merged = merge_input(existing, data, EXIT_EDIT_FIELDS)
    result = validate_exit(
        db,
        merged,
        existing,
        confirm_new_customer=bool(confirms.get("confirm_new_customer")),
        confirm_new_supplier=bool(confirms.get("confirm_new_supplier")),
    )
    if result.field_errors:
        raise AppError(422, result.payload())
    row = apply_exit(db, result, user, request, existing)
    db.commit()
    return {"item": exit_out(row), "warnings": result.warnings}


def next_exit_no(db: Session) -> int:
    current = db.scalar(select(func.max(ExitRecord.no)))
    return int(current or 0) + 1


def visible(row, user: User):
    if row is None or (row.deleted_at is not None and user.role != "admin"):
        raise AppError(404, {"message": "Not found"})
    return row


def require_row(row):
    if row is None:
        raise AppError(404, {"message": "Not found"})
    return row


def _filtered(model, filters: list):
    count_stmt = select(func.count()).select_from(model)
    stmt = select(model)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    return count_stmt, stmt


def list_cargo(
    db: Session,
    kind: str,
    *,
    q: str | None,
    needs_review: bool | None,
    stage: str | None,
    shipping_route: str | None,
    status: str | None,
    include_deleted: bool,
    limit: int,
    offset: int,
    user: User,
) -> dict:
    model = SeaCargo if kind == "sea" else AirCargo
    filters = []
    if not (include_deleted and user.role == "admin"):
        filters.append(model.deleted_at.is_(None))
    if needs_review is not None:
        filters.append(model.needs_review.is_(needs_review))
    if q and q.strip():
        pattern = like_pattern(q.strip())
        columns = [model.customer_code, model.company_name, model.system_code, model.shipment_number]
        if kind == "sea":
            columns.append(model.shipping_route)
            columns.append(model.stage)
        else:
            columns.append(model.status)
        filters.append(or_(*[column.ilike(pattern, escape="\\") for column in columns]))
    if kind == "sea" and stage:
        filters.append(model.stage == stage)
    if kind == "sea" and shipping_route:
        filters.append(model.shipping_route == shipping_route)
    if kind == "air" and status:
        filters.append(model.status == status)
    count_stmt, stmt = _filtered(model, filters)
    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(model.date_received.is_(None), model.date_received.desc(), model.id.desc())
    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return {"items": [cargo_out(row, kind) for row in rows], "total": total}


def list_exit(
    db: Session,
    *,
    q: str | None,
    needs_review: bool | None,
    status: str | None,
    include_deleted: bool,
    limit: int,
    offset: int,
    user: User,
) -> dict:
    filters = []
    if not (include_deleted and user.role == "admin"):
        filters.append(ExitRecord.deleted_at.is_(None))
    if needs_review is not None:
        filters.append(ExitRecord.needs_review.is_(needs_review))
    if status:
        filters.append(ExitRecord.status == status)
    if q and q.strip():
        pattern = like_pattern(q.strip())
        clauses = [
            ExitRecord.mark.ilike(pattern, escape="\\"),
            ExitRecord.supplier.ilike(pattern, escape="\\"),
            ExitRecord.invoice_no.ilike(pattern, escape="\\"),
            ExitRecord.status.ilike(pattern, escape="\\"),
        ]
        if q.strip().isdigit():
            clauses.append(ExitRecord.no == int(q.strip()))
        filters.append(or_(*clauses))
    count_stmt, stmt = _filtered(ExitRecord, filters)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(ExitRecord.no.desc()).offset(offset).limit(limit)).all()
    return {"items": [exit_out(row) for row in rows], "total": total}


def mark_deleted(db: Session, row, user: User, request, entity_type: str, fields: list[str]) -> None:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Row is already deleted"})
    before = snapshot(row, fields)
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.deleted_by = user.id
    row.updated_at = now
    row.updated_by = user.id
    db.flush()
    after = snapshot(row, fields)
    write_audit(
        db,
        actor_user_id=user.id,
        action="delete",
        entity_type=entity_type,
        entity_id=row.id,
        before=before,
        after=after,
        changed=diff(before, after, fields),
        request=request,
    )
    db.commit()


def mark_restored(db: Session, row, user: User, request, entity_type: str, fields: list[str]) -> None:
    if row.deleted_at is None:
        raise AppError(400, {"message": "Row is not deleted"})
    before = snapshot(row, fields)
    now = datetime.now(timezone.utc)
    row.deleted_at = None
    row.deleted_by = None
    row.updated_at = now
    row.updated_by = user.id
    db.flush()
    after = snapshot(row, fields)
    write_audit(
        db,
        actor_user_id=user.id,
        action="restore",
        entity_type=entity_type,
        entity_id=row.id,
        before=before,
        after=after,
        changed=diff(before, after, fields),
        request=request,
    )
    db.commit()
