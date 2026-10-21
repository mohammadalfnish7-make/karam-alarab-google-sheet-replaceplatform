"""CRUD for standalone image invoices (product rows from photos)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.cargo_files import IMAGE_INVOICE_LINE_ENTITY, counts_for, soft_delete_file
from app.errors import AppError
from app.models import CargoFile, ImageInvoice, ImageInvoiceLine, User
from app.present import diff, iso, num, snapshot
from app.records import mark_deleted, mark_restored

ENTITY = "image_invoice"
FIELDS = ["title", "deleted_at", "deleted_by"]
LINE_FIELDS = ["sort_order", "brand_name", "barcode", "made_in", "volume", "quantity"]


def line_out(row: ImageInvoiceLine, *, file_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "image_invoice_id": row.image_invoice_id,
        "sort_order": row.sort_order,
        "brand_name": row.brand_name,
        "barcode": row.barcode,
        "made_in": row.made_in,
        "volume": row.volume,
        "quantity": num(row.quantity),
        "file_count": file_count,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
    }


def invoice_out(
    row: ImageInvoice,
    *,
    lines: list[dict[str, Any]] | None = None,
    line_count: int | None = None,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "line_count": line_count if line_count is not None else (len(lines) if lines is not None else 0),
        "lines": lines,
        "created_at": iso(row.created_at),
        "created_by": row.created_by,
        "updated_at": iso(row.updated_at),
        "updated_by": row.updated_by,
        "deleted_at": iso(row.deleted_at),
        "deleted_by": row.deleted_by,
    }


def get_invoice(db: Session, item_id: int, user: User) -> ImageInvoice:
    row = db.get(ImageInvoice, item_id)
    if row is None or (row.deleted_at is not None and user.role != "admin"):
        raise AppError(404, {"message": "Not found"})
    return row


def get_line(db: Session, invoice_id: int, line_id: int, user: User) -> ImageInvoiceLine:
    get_invoice(db, invoice_id, user)
    line = db.get(ImageInvoiceLine, line_id)
    if line is None or line.image_invoice_id != invoice_id:
        raise AppError(404, {"message": "Line not found"})
    return line


def _lines_for(db: Session, invoice_id: int) -> list[ImageInvoiceLine]:
    return list(
        db.scalars(
            select(ImageInvoiceLine)
            .where(ImageInvoiceLine.image_invoice_id == invoice_id)
            .order_by(ImageInvoiceLine.sort_order.asc(), ImageInvoiceLine.id.asc())
        ).all()
    )


def _lines_out(db: Session, invoice_id: int) -> list[dict[str, Any]]:
    lines = _lines_for(db, invoice_id)
    counts = counts_for(db, IMAGE_INVOICE_LINE_ENTITY, [line.id for line in lines])
    return [line_out(line, file_count=counts.get(line.id, 0)) for line in lines]


def list_rows(
    db: Session,
    *,
    q: str | None,
    include_deleted: bool,
    limit: int,
    offset: int,
    user: User,
) -> dict[str, Any]:
    stmt = select(ImageInvoice)
    count_stmt = select(func.count()).select_from(ImageInvoice)
    if not include_deleted or user.role != "admin":
        stmt = stmt.where(ImageInvoice.deleted_at.is_(None))
        count_stmt = count_stmt.where(ImageInvoice.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(ImageInvoice.title.ilike(like)))
        count_stmt = count_stmt.where(or_(ImageInvoice.title.ilike(like)))
    total = db.scalar(count_stmt) or 0
    rows = list(db.scalars(stmt.order_by(ImageInvoice.id.desc()).offset(offset).limit(limit)).all())
    items = []
    for row in rows:
        line_count = db.scalar(
            select(func.count()).select_from(ImageInvoiceLine).where(
                ImageInvoiceLine.image_invoice_id == row.id
            )
        ) or 0
        items.append(invoice_out(row, line_count=int(line_count), lines=None))
    return {"items": items, "total": total}


def create_row(db: Session, data: dict[str, Any], user: User, request) -> dict[str, Any]:
    title = str(data.get("title") or "").strip() or None
    now = datetime.now(timezone.utc)
    row = ImageInvoice(
        title=title or f"Image invoice {now.strftime('%Y-%m-%d %H:%M')}",
        created_at=now,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type=ENTITY,
        entity_id=row.id,
        before=None,
        after=snapshot(row, FIELDS),
        changed=[{"field": "title", "old": None, "new": row.title}],
        request=request,
    )
    db.commit()
    db.refresh(row)
    return {"item": invoice_out(row, lines=[], line_count=0)}


def update_header(db: Session, row: ImageInvoice, data: dict[str, Any], user: User, request) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    if "title" in data:
        row.title = str(data.get("title") or "").strip() or row.title
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = user.id
    db.flush()
    after = snapshot(row, FIELDS)
    write_audit(
        db,
        actor_user_id=user.id,
        action="update",
        entity_type=ENTITY,
        entity_id=row.id,
        before=before,
        after=after,
        changed=diff(before, after, FIELDS),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return {"item": invoice_out(row, lines=_lines_out(db, row.id))}


def get_detail(db: Session, row: ImageInvoice) -> dict[str, Any]:
    lines = _lines_out(db, row.id)
    return {"item": invoice_out(row, lines=lines, line_count=len(lines))}


def _parse_quantity(raw: Any) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        value = Decimal(str(raw).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        raise AppError(422, {"field_errors": {"quantity": "Quantity must be a number"}}) from None
    if value < 0:
        raise AppError(422, {"field_errors": {"quantity": "Quantity must be 0 or greater"}})
    return value


def _text_or_none(raw: Any) -> str | None:
    text = str(raw or "").strip()
    return text or None


def add_line(db: Session, invoice: ImageInvoice, user: User, request) -> dict[str, Any]:
    if invoice.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    max_order = db.scalar(
        select(func.max(ImageInvoiceLine.sort_order)).where(
            ImageInvoiceLine.image_invoice_id == invoice.id
        )
    )
    now = datetime.now(timezone.utc)
    line = ImageInvoiceLine(
        image_invoice_id=invoice.id,
        sort_order=(max_order or 0) + 1,
        created_at=now,
    )
    db.add(line)
    invoice.updated_at = now
    invoice.updated_by = user.id
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="add_line",
        entity_type=ENTITY,
        entity_id=invoice.id,
        before=None,
        after={"line_id": line.id},
        changed=[{"field": "lines", "old": None, "new": f"added #{line.id}"}],
        request=request,
    )
    db.commit()
    db.refresh(line)
    return {"item": line_out(line, file_count=0)}


def save_lines(
    db: Session,
    invoice: ImageInvoice,
    body: dict[str, Any],
    user: User,
    request,
) -> dict[str, Any]:
    if invoice.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    raw_lines = body.get("lines")
    if not isinstance(raw_lines, list):
        raise AppError(422, {"field_errors": {"lines": "Lines must be a list"}})

    existing = {line.id: line for line in _lines_for(db, invoice.id)}
    keep_ids: set[int] = set()
    field_errors: dict[str, str] = {}

    for index, raw in enumerate(raw_lines):
        if not isinstance(raw, dict):
            field_errors[f"lines.{index}"] = "Invalid row"
            continue
        line_id = raw.get("id")
        try:
            quantity = _parse_quantity(raw.get("quantity"))
        except AppError as exc:
            err = exc.body.get("field_errors", {}) if isinstance(exc.body, dict) else {}
            field_errors[f"lines.{index}.quantity"] = err.get("quantity") or "Invalid quantity"
            continue
        brand = _text_or_none(raw.get("brand_name"))
        barcode = _text_or_none(raw.get("barcode"))
        made_in = _text_or_none(raw.get("made_in"))
        volume = _text_or_none(raw.get("volume"))
        sort_order = index + 1
        try:
            if raw.get("sort_order") not in (None, ""):
                sort_order = int(raw.get("sort_order"))
        except (TypeError, ValueError):
            sort_order = index + 1

        if line_id not in (None, ""):
            try:
                lid = int(line_id)
            except (TypeError, ValueError):
                field_errors[f"lines.{index}.id"] = "Invalid line id"
                continue
            line = existing.get(lid)
            if line is None:
                field_errors[f"lines.{index}.id"] = "Line not found"
                continue
            line.sort_order = sort_order
            line.brand_name = brand
            line.barcode = barcode
            line.made_in = made_in
            line.volume = volume
            line.quantity = quantity
            line.updated_at = datetime.now(timezone.utc)
            keep_ids.add(lid)
        else:
            now = datetime.now(timezone.utc)
            line = ImageInvoiceLine(
                image_invoice_id=invoice.id,
                sort_order=sort_order,
                brand_name=brand,
                barcode=barcode,
                made_in=made_in,
                volume=volume,
                quantity=quantity,
                created_at=now,
            )
            db.add(line)
            db.flush()
            keep_ids.add(line.id)

    if field_errors:
        raise AppError(422, {"message": "Fix line errors", "field_errors": field_errors})

    for lid, line in existing.items():
        if lid not in keep_ids:
            _soft_delete_line_files(db, lid, user)
            db.delete(line)

    invoice.updated_at = datetime.now(timezone.utc)
    invoice.updated_by = user.id
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="save_lines",
        entity_type=ENTITY,
        entity_id=invoice.id,
        before=None,
        after={"line_count": len(keep_ids)},
        changed=[{"field": "lines", "old": None, "new": f"{len(keep_ids)} lines"}],
        request=request,
    )
    db.commit()
    db.refresh(invoice)
    return get_detail(db, invoice)


def _soft_delete_line_files(db: Session, line_id: int, user: User) -> None:
    files = db.scalars(
        select(CargoFile).where(
            CargoFile.entity_type == IMAGE_INVOICE_LINE_ENTITY,
            CargoFile.entity_id == str(line_id),
            CargoFile.deleted_at.is_(None),
        )
    ).all()
    for file_row in files:
        soft_delete_file(db, file_row, user)


def delete_line(db: Session, invoice: ImageInvoice, line: ImageInvoiceLine, user: User, request) -> dict[str, Any]:
    if invoice.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    line_id = line.id
    _soft_delete_line_files(db, line_id, user)
    db.delete(line)
    invoice.updated_at = datetime.now(timezone.utc)
    invoice.updated_by = user.id
    write_audit(
        db,
        actor_user_id=user.id,
        action="delete_line",
        entity_type=ENTITY,
        entity_id=invoice.id,
        before={"line_id": line_id},
        after=None,
        changed=[{"field": "lines", "old": f"#{line_id}", "new": "deleted"}],
        request=request,
    )
    db.commit()
    return get_detail(db, invoice)


def delete_row(db: Session, row: ImageInvoice, user: User, request) -> dict[str, Any]:
    mark_deleted(db, row, user, request, ENTITY, FIELDS)
    db.refresh(row)
    return {"item": invoice_out(row, line_count=0, lines=None)}


def restore_row(db: Session, row: ImageInvoice, user: User, request) -> dict[str, Any]:
    mark_restored(db, row, user, request, ENTITY, FIELDS)
    db.refresh(row)
    return get_detail(db, row)
