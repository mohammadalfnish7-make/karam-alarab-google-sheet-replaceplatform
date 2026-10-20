"""CRUD for standalone air shipment picture records."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.cargo_files import AIR_PICTURE_ENTITY, counts_for
from app.errors import AppError
from app.models import AirShipmentPicture, User
from app.present import diff, iso, snapshot
from app.records import mark_deleted, mark_restored

FIELDS = ["number", "date", "cartons", "deleted_at", "deleted_by"]
ENTITY = "air_shipment_picture"
_NUMBER_RE = re.compile(r"^AR([0-9]+)$", re.IGNORECASE)


def next_number(db: Session) -> str:
    stored = db.scalars(
        select(AirShipmentPicture.number).where(
            AirShipmentPicture.deleted_at.is_(None),
            AirShipmentPicture.number.is_not(None),
        )
    )
    highest = 0
    for value in stored:
        if not value:
            continue
        match = _NUMBER_RE.fullmatch(value.strip())
        if not match:
            continue
        number = int(match.group(1))
        if number > highest:
            highest = number
    next_value = highest + 1
    return f"AR{next_value:03d}"


def picture_out(row: AirShipmentPicture, *, file_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "number": row.number,
        "date": iso(row.date),
        "cartons": row.cartons,
        "file_count": file_count,
        "created_at": iso(row.created_at),
        "created_by": row.created_by,
        "updated_at": iso(row.updated_at),
        "updated_by": row.updated_by,
        "deleted_at": iso(row.deleted_at),
        "deleted_by": row.deleted_by,
    }


def get_row(db: Session, item_id: int, user: User) -> AirShipmentPicture:
    row = db.get(AirShipmentPicture, item_id)
    if row is None or (row.deleted_at is not None and user.role != "admin"):
        raise AppError(404, {"message": "Not found"})
    return row


def _normalize_number(raw: Any) -> str:
    text = str(raw or "").strip().upper()
    if not text:
        raise AppError(422, {"field_errors": {"number": "Number is required"}})
    match = _NUMBER_RE.fullmatch(text)
    if not match:
        raise AppError(422, {"field_errors": {"number": "Number must look like AR087"}})
    digits = match.group(1)
    # Keep at least 3 digits (AR087); allow longer if user enters more
    if len(digits) < 3:
        digits = digits.zfill(3)
    return f"AR{digits}"


def _number_taken(db: Session, number: str, exclude_id: int | None = None) -> bool:
    stmt = select(AirShipmentPicture.id).where(
        func.lower(AirShipmentPicture.number) == number.lower(),
        AirShipmentPicture.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(AirShipmentPicture.id != exclude_id)
    return db.scalar(stmt) is not None


def _parse_date(raw: Any, *, default_today: bool) -> date:
    if raw in (None, "") and default_today:
        return date.today()
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw or "").strip()
    if not text:
        if default_today:
            return date.today()
        raise AppError(422, {"field_errors": {"date": "Date is required"}})
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise AppError(422, {"field_errors": {"date": "Date must be YYYY-MM-DD"}}) from exc


def _parse_cartons(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    text = str(raw).strip().upper().replace("CTN", "").strip()
    try:
        value = int(float(text))
    except (TypeError, ValueError) as exc:
        raise AppError(422, {"field_errors": {"cartons": "Cartons must be a whole number"}}) from exc
    if value < 0:
        raise AppError(422, {"field_errors": {"cartons": "Cartons cannot be negative"}})
    return value


def list_rows(
    db: Session,
    *,
    q: str | None,
    include_deleted: bool,
    limit: int,
    offset: int,
    user: User,
) -> dict[str, Any]:
    stmt = select(AirShipmentPicture)
    count_stmt = select(func.count()).select_from(AirShipmentPicture)
    if not include_deleted or user.role != "admin":
        stmt = stmt.where(AirShipmentPicture.deleted_at.is_(None))
        count_stmt = count_stmt.where(AirShipmentPicture.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        filt = or_(AirShipmentPicture.number.ilike(like))
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(AirShipmentPicture.id.desc()).offset(offset).limit(limit)).all()
    counts = counts_for(db, AIR_PICTURE_ENTITY, [row.id for row in rows])
    return {
        "items": [picture_out(row, file_count=counts.get(row.id, 0)) for row in rows],
        "total": total,
    }


def create_row(db: Session, body: dict[str, Any], user: User, request) -> dict[str, Any]:
    number = body.get("number")
    number = _normalize_number(number) if number not in (None, "") else next_number(db)
    if _number_taken(db, number):
        raise AppError(422, {"field_errors": {"number": "Number already exists"}})
    row_date = _parse_date(body.get("date"), default_today=True)
    cartons = _parse_cartons(body.get("cartons")) if "cartons" in body else None
    now = datetime.now(timezone.utc)
    row = AirShipmentPicture(
        number=number,
        date=row_date,
        cartons=cartons,
        created_at=now,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    after = snapshot(row, FIELDS)
    write_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type=ENTITY,
        entity_id=row.id,
        before=None,
        after=after,
        changed=diff({}, after, FIELDS),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return {"item": picture_out(row)}


def update_row(
    db: Session,
    row: AirShipmentPicture,
    body: dict[str, Any],
    user: User,
    request,
) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    if "number" in body and body["number"] is not None:
        number = _normalize_number(body["number"])
        if _number_taken(db, number, exclude_id=row.id):
            raise AppError(422, {"field_errors": {"number": "Number already exists"}})
        row.number = number
    if "date" in body:
        row.date = _parse_date(body.get("date"), default_today=False)
    if "cartons" in body:
        row.cartons = _parse_cartons(body.get("cartons"))
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
    return {
        "item": picture_out(
            row,
            file_count=counts_for(db, AIR_PICTURE_ENTITY, [row.id]).get(row.id, 0),
        )
    }


def delete_row(db: Session, item_id: int, user: User, request) -> dict[str, Any]:
    row = get_row(db, item_id, user)
    mark_deleted(db, row, user, request, ENTITY, FIELDS)
    return {"item": picture_out(row)}


def restore_row(db: Session, item_id: int, user: User, request) -> dict[str, Any]:
    row = db.get(AirShipmentPicture, item_id)
    if row is None:
        raise AppError(404, {"message": "Not found"})
    if row.number and _number_taken(db, row.number, exclude_id=row.id):
        raise AppError(422, {"field_errors": {"number": "Number already exists"}})
    mark_restored(db, row, user, request, ENTITY, FIELDS)
    return {"item": picture_out(row)}
