"""Document expiry reminders and urgency helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.errors import AppError
from app.models import DocumentExpiry, User
from app.validation import parse_api_date, parse_dmy

URGENT_DAYS = 30
SOON_DAYS = 90
ENTITY_TYPE = "document_expiry"


def urgency(expiry: date | None, *, today: date | None = None) -> dict:
    today = today or date.today()
    if expiry is None:
        return {"status": "unknown", "days_left": None, "label": "No date"}
    days = (expiry - today).days
    if days < 0:
        return {"status": "expired", "days_left": days, "label": f"Expired {abs(days)}d ago"}
    if days == 0:
        return {"status": "urgent", "days_left": 0, "label": "Expires today"}
    if days <= URGENT_DAYS:
        return {"status": "urgent", "days_left": days, "label": f"Due in {days}d"}
    if days <= SOON_DAYS:
        return {"status": "soon", "days_left": days, "label": f"Due in {days}d"}
    return {"status": "ok", "days_left": days, "label": f"Due in {days}d"}


def item_out(row: DocumentExpiry, *, today: date | None = None) -> dict:
    flag = urgency(row.expiry_date, today=today)
    return {
        "id": row.id,
        "category": row.category,
        "sl_no": row.sl_no,
        "title": row.title,
        "document_type": row.document_type,
        "document_no": row.document_no,
        "company_name": row.company_name,
        "holder_name": row.holder_name,
        "plate_no": row.plate_no,
        "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
        "status": flag["status"],
        "days_left": flag["days_left"],
        "status_label": flag["label"],
    }


def list_expiry(
    db: Session,
    *,
    category: str | None = None,
    status: str | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    stmt = select(DocumentExpiry)
    if category:
        stmt = stmt.where(DocumentExpiry.category == category)
    rows = db.scalars(stmt).all()
    items = [item_out(row, today=today) for row in rows]
    if status:
        items = [item for item in items if item["status"] == status]

    def sort_key(item: dict):
        days = item["days_left"]
        if days is None:
            return (2, 10_000)
        if days < 0:
            return (0, days)
        return (1, days)

    items.sort(key=sort_key)
    summary = {
        "total": len(items),
        "expired": sum(1 for item in items if item["status"] == "expired"),
        "urgent": sum(1 for item in items if item["status"] == "urgent"),
        "soon": sum(1 for item in items if item["status"] == "soon"),
        "ok": sum(1 for item in items if item["status"] == "ok"),
        "unknown": sum(1 for item in items if item["status"] == "unknown"),
    }
    return {"items": items, "summary": summary, "as_of": today.isoformat()}


def require_expiry(db: Session, item_id: int) -> DocumentExpiry:
    row = db.get(DocumentExpiry, item_id)
    if row is None:
        raise AppError(404, {"message": "Document not found"})
    return row


def _snapshot(row: DocumentExpiry) -> dict:
    return {
        "id": row.id,
        "category": row.category,
        "sl_no": row.sl_no,
        "title": row.title,
        "document_type": row.document_type,
        "document_no": row.document_no,
        "company_name": row.company_name,
        "holder_name": row.holder_name,
        "plate_no": row.plate_no,
        "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
    }


def parse_expiry_date(value) -> date | None:
    """Accept ISO, DD/MM/YYYY, or blank (clears the date)."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, str):
        text = value.strip()
        parsed = parse_dmy(text)
        if parsed:
            return parsed
    parsed, error = parse_api_date(value)
    if error:
        raise AppError(422, {"message": error, "field_errors": {"expiry_date": error}})
    return parsed


def update_expiry_date(
    db: Session,
    row: DocumentExpiry,
    *,
    expiry_date: date | None,
    user: User,
    request,
) -> dict:
    before = _snapshot(row)
    if row.expiry_date == expiry_date:
        return item_out(row)
    row.expiry_date = expiry_date
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    after = _snapshot(row)
    write_audit(
        db,
        actor_user_id=user.id,
        action="update",
        entity_type=ENTITY_TYPE,
        entity_id=row.id,
        before=before,
        after=after,
        changed=[{"field": "expiry_date", "old": before["expiry_date"], "new": after["expiry_date"]}],
        request=request,
    )
    db.commit()
    db.refresh(row)
    return item_out(row)
