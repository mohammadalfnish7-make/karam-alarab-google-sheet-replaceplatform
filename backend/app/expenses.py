"""CRUD for standalone Qusai expenses (amount + currency + notes + photos)."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.cargo_files import EXPENSE_ENTITY, counts_for
from app.errors import AppError
from app.models import Expense, User
from app.present import diff, freeze, iso, num, snapshot
from app.records import mark_deleted, mark_restored

FIELDS = ["mark", "date", "amount", "currency", "notes", "summary_json", "deleted_at", "deleted_by"]
ENTITY = "expense"
BUDGET_LIMIT_AED = Decimal("2000")
_MARK_RE = re.compile(r"^EX([0-9]+)$", re.IGNORECASE)
_CURRENCIES = {"AED", "USD", "EUR"}


def next_mark(db: Session) -> str:
    stored = db.scalars(
        select(Expense.mark).where(Expense.deleted_at.is_(None), Expense.mark.is_not(None))
    )
    highest = 0
    for value in stored:
        if not value:
            continue
        match = _MARK_RE.fullmatch(value.strip())
        if not match:
            continue
        number = int(match.group(1))
        if number > highest:
            highest = number
    return f"EX{highest + 1}"


def expense_out(row: Expense, *, file_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "mark": row.mark,
        "date": iso(row.date),
        "amount": num(row.amount),
        "currency": row.currency,
        "notes": row.notes,
        "summary": row.summary_json,
        "file_count": file_count,
        "created_at": iso(row.created_at),
        "created_by": row.created_by,
        "updated_at": iso(row.updated_at),
        "updated_by": row.updated_by,
        "deleted_at": iso(row.deleted_at),
        "deleted_by": row.deleted_by,
    }


def get_row(db: Session, item_id: int, user: User) -> Expense:
    row = db.get(Expense, item_id)
    if row is None or (row.deleted_at is not None and user.role != "admin"):
        raise AppError(404, {"message": "Not found"})
    return row


def _normalize_mark(raw: Any) -> str:
    mark = str(raw or "").strip().upper()
    if not mark:
        raise AppError(422, {"field_errors": {"mark": "Mark is required"}})
    if not _MARK_RE.fullmatch(mark):
        raise AppError(422, {"field_errors": {"mark": "Mark must look like EX123"}})
    return mark


def _mark_taken(db: Session, mark: str, exclude_id: int | None = None) -> bool:
    stmt = select(Expense.id).where(
        func.lower(Expense.mark) == mark.lower(),
        Expense.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(Expense.id != exclude_id)
    return db.scalar(stmt) is not None


def _parse_amount(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        value = Decimal(str(raw).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        raise AppError(422, {"field_errors": {"amount": "Amount must be a number"}}) from None
    if value <= 0:
        raise AppError(422, {"field_errors": {"amount": "Amount must be greater than 0"}})
    return value


def _parse_currency(raw: Any) -> str:
    currency = str(raw or "AED").strip().upper() or "AED"
    if currency not in _CURRENCIES:
        raise AppError(422, {"field_errors": {"currency": "Currency must be AED, USD, or EUR"}})
    return currency


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


def aed_spent(db: Session, *, exclude_id: int | None = None) -> Decimal:
    stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.deleted_at.is_(None),
        func.upper(Expense.currency) == "AED",
        Expense.amount.is_not(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(Expense.id != exclude_id)
    total = db.scalar(stmt) or 0
    return Decimal(str(total))


def budget(db: Session) -> dict[str, Any]:
    spent = aed_spent(db)
    remaining = BUDGET_LIMIT_AED - spent
    if remaining < 0:
        remaining = Decimal("0")
    return {
        "limit": freeze(BUDGET_LIMIT_AED),
        "spent": freeze(spent),
        "remaining": freeze(remaining),
        "currency": "AED",
    }


def _ensure_budget(db: Session, amount: Decimal | None, currency: str, *, exclude_id: int | None = None) -> None:
    if amount is None or currency != "AED":
        return
    spent = aed_spent(db, exclude_id=exclude_id)
    if spent + amount > BUDGET_LIMIT_AED:
        remaining = BUDGET_LIMIT_AED - spent
        if remaining < 0:
            remaining = Decimal("0")
        raise AppError(
            422,
            {
                "message": f"Qusai AED budget is 2000. Remaining {freeze(remaining)} AED.",
                "field_errors": {"amount": "Would exceed 2000 AED budget"},
                "code": "budget_exceeded",
            },
        )


def list_rows(
    db: Session,
    *,
    q: str | None,
    include_deleted: bool,
    limit: int,
    offset: int,
    user: User,
) -> dict[str, Any]:
    stmt = select(Expense)
    count_stmt = select(func.count()).select_from(Expense)
    if not include_deleted or user.role != "admin":
        stmt = stmt.where(Expense.deleted_at.is_(None))
        count_stmt = count_stmt.where(Expense.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        filt = or_(Expense.mark.ilike(like), Expense.notes.ilike(like), Expense.currency.ilike(like))
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Expense.id.desc()).offset(offset).limit(limit)).all()
    counts = counts_for(db, EXPENSE_ENTITY, [row.id for row in rows])
    return {
        "items": [expense_out(row, file_count=counts.get(row.id, 0)) for row in rows],
        "total": total,
        "budget": budget(db),
    }


def create_row(db: Session, body: dict[str, Any], user: User, request) -> dict[str, Any]:
    mark = body.get("mark")
    mark = _normalize_mark(mark) if mark not in (None, "") else next_mark(db)
    if _mark_taken(db, mark):
        raise AppError(422, {"field_errors": {"mark": "Mark already exists"}})
    expense_date = _parse_date(body.get("date"), default_today=True)
    amount = _parse_amount(body.get("amount")) if "amount" in body else None
    currency = _parse_currency(body.get("currency"))
    notes = body.get("notes")
    notes = None if notes in (None, "") else str(notes).strip()
    _ensure_budget(db, amount, currency)
    now = datetime.now(timezone.utc)
    row = Expense(
        mark=mark,
        date=expense_date,
        amount=amount,
        currency=currency,
        notes=notes,
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
        changed=diff({}, snapshot(row, FIELDS), FIELDS),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return {"item": expense_out(row), "budget": budget(db)}


def update_row(db: Session, row: Expense, body: dict[str, Any], user: User, request) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    if "mark" in body and body["mark"] is not None:
        mark = _normalize_mark(body["mark"])
        if _mark_taken(db, mark, exclude_id=row.id):
            raise AppError(422, {"field_errors": {"mark": "Mark already exists"}})
        row.mark = mark
    if "date" in body:
        row.date = _parse_date(body.get("date"), default_today=False)
    amount = row.amount
    currency = row.currency
    if "amount" in body:
        amount = _parse_amount(body.get("amount"))
        row.amount = amount
    if "currency" in body:
        currency = _parse_currency(body.get("currency"))
        row.currency = currency
    if "notes" in body:
        value = body["notes"]
        row.notes = None if value in (None, "") else str(value).strip()
    _ensure_budget(
        db,
        Decimal(str(amount)) if amount is not None else None,
        currency,
        exclude_id=row.id,
    )
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
        "item": expense_out(row, file_count=counts_for(db, EXPENSE_ENTITY, [row.id]).get(row.id, 0)),
        "budget": budget(db),
    }


def delete_row(db: Session, item_id: int, user: User, request) -> dict[str, Any]:
    row = get_row(db, item_id, user)
    mark_deleted(db, row, user, request, ENTITY, FIELDS)
    return {"item": expense_out(row), "budget": budget(db)}


def restore_row(db: Session, item_id: int, user: User, request) -> dict[str, Any]:
    row = db.get(Expense, item_id)
    if row is None:
        raise AppError(404, {"message": "Not found"})
    if row.mark and _mark_taken(db, row.mark, exclude_id=row.id):
        raise AppError(422, {"field_errors": {"mark": "Mark already exists"}})
    amount = Decimal(str(row.amount)) if row.amount is not None else None
    _ensure_budget(db, amount, (row.currency or "AED").upper(), exclude_id=row.id)
    mark_restored(db, row, user, request, ENTITY, FIELDS)
    return {"item": expense_out(row), "budget": budget(db)}
