"""CRUD for standalone container loading records (mark + container_no + photos)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.cargo_files import LOADING_ENTITY, counts_for
from app.errors import AppError
from app.models import ContainerLoading, User
from app.present import diff, snapshot
from app.records import mark_deleted, mark_restored

FIELDS = [
    "mark",
    "container_no",
    "container_row_id",
    "plan_json",
    "plan_filename",
    "check_json",
    "summary_json",
    "deleted_at",
    "deleted_by",
]
ENTITY = "container_loading"
_MARK_RE = re.compile(r"^CL([0-9]+)$", re.IGNORECASE)


def next_mark(db: Session) -> str:
    stored = db.scalars(
        select(ContainerLoading.mark).where(
            ContainerLoading.deleted_at.is_(None),
            ContainerLoading.mark.is_not(None),
        )
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
    return f"CL{highest + 1}"


def loading_out(row: ContainerLoading, *, file_count: int = 0) -> dict[str, Any]:
    plan = row.plan_json if isinstance(row.plan_json, dict) else None
    return {
        "id": row.id,
        "mark": row.mark,
        "container_no": row.container_no,
        "container_row_id": row.container_row_id,
        "plan": plan,
        "plan_filename": row.plan_filename,
        "plan_line_count": (plan or {}).get("line_count") if plan else 0,
        "check": row.check_json,
        "summary": row.summary_json,
        "file_count": file_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
        "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
        "deleted_by": row.deleted_by,
    }


def get_row(db: Session, item_id: int, user: User) -> ContainerLoading:
    row = db.get(ContainerLoading, item_id)
    if row is None or (row.deleted_at is not None and user.role != "admin"):
        raise AppError(404, {"message": "Not found"})
    return row


def _normalize_mark(raw: Any) -> str:
    mark = str(raw or "").strip()
    if not mark:
        raise AppError(422, {"field_errors": {"mark": "Mark is required"}})
    if len(mark) > 64:
        raise AppError(422, {"field_errors": {"mark": "Mark is too long"}})
    return mark


def _mark_taken(db: Session, mark: str, exclude_id: int | None = None) -> bool:
    stmt = select(ContainerLoading.id).where(
        func.lower(ContainerLoading.mark) == mark.lower(),
        ContainerLoading.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(ContainerLoading.id != exclude_id)
    return db.scalar(stmt) is not None


def list_rows(
    db: Session,
    *,
    q: str | None,
    include_deleted: bool,
    limit: int,
    offset: int,
    user: User,
) -> dict[str, Any]:
    stmt = select(ContainerLoading)
    count_stmt = select(func.count()).select_from(ContainerLoading)
    if not include_deleted or user.role != "admin":
        stmt = stmt.where(ContainerLoading.deleted_at.is_(None))
        count_stmt = count_stmt.where(ContainerLoading.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        filt = or_(ContainerLoading.mark.ilike(like), ContainerLoading.container_no.ilike(like))
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(ContainerLoading.id.desc()).offset(offset).limit(limit)).all()
    counts = counts_for(db, LOADING_ENTITY, [row.id for row in rows])
    return {
        "items": [loading_out(row, file_count=counts.get(row.id, 0)) for row in rows],
        "total": total,
    }


def create_row(db: Session, body: dict[str, Any], user: User, request) -> dict[str, Any]:
    mark = body.get("mark")
    mark = _normalize_mark(mark) if mark not in (None, "") else next_mark(db)
    if _mark_taken(db, mark):
        raise AppError(422, {"field_errors": {"mark": "Mark already exists"}})
    container_no = body.get("container_no")
    container_no = None if container_no in (None, "") else str(container_no).strip()
    now = datetime.now(timezone.utc)
    row = ContainerLoading(
        mark=mark,
        container_no=container_no,
        container_row_id=None,
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
        changed=FIELDS,
        request=request,
    )
    db.commit()
    db.refresh(row)
    return {"item": loading_out(row)}


def update_row(db: Session, row: ContainerLoading, body: dict[str, Any], user: User, request) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    if "mark" in body and body["mark"] is not None:
        mark = _normalize_mark(body["mark"])
        if _mark_taken(db, mark, exclude_id=row.id):
            raise AppError(422, {"field_errors": {"mark": "Mark already exists"}})
        row.mark = mark
    if "container_no" in body:
        value = body["container_no"]
        row.container_no = None if value in (None, "") else str(value).strip()
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
    return {"item": loading_out(row, file_count=counts_for(db, LOADING_ENTITY, [row.id]).get(row.id, 0))}


def delete_row(db: Session, item_id: int, user: User, request) -> dict[str, Any]:
    row = get_row(db, item_id, user)
    mark_deleted(db, row, user, request, ENTITY, FIELDS)
    return {"item": loading_out(row)}


def restore_row(db: Session, item_id: int, user: User, request) -> dict[str, Any]:
    row = db.get(ContainerLoading, item_id)
    if row is None:
        raise AppError(404, {"message": "Not found"})
    if row.mark and _mark_taken(db, row.mark, exclude_id=row.id):
        raise AppError(422, {"field_errors": {"mark": "Mark already exists"}})
    mark_restored(db, row, user, request, ENTITY, FIELDS)
    return {"item": loading_out(row)}


def set_plan(
    db: Session,
    row: ContainerLoading,
    plan: dict[str, Any],
    *,
    filename: str | None,
    user: User,
    request,
) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    row.plan_json = plan
    row.plan_filename = filename
    row.check_json = None
    if not row.container_no and plan.get("container_number"):
        row.container_no = str(plan["container_number"]).strip()
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = user.id
    db.flush()
    after = snapshot(row, FIELDS)
    write_audit(
        db,
        actor_user_id=user.id,
        action="upload_plan",
        entity_type=ENTITY,
        entity_id=row.id,
        before=before,
        after=after,
        changed=[
            {
                "field": "plan",
                "old": None,
                "new": f"{filename or 'plan.xlsx'} ({plan.get('line_count') or 0} lines)",
            }
        ],
        request=request,
    )
    db.commit()
    db.refresh(row)
    return {
        "item": loading_out(
            row,
            file_count=counts_for(db, LOADING_ENTITY, [row.id]).get(row.id, 0),
        )
    }


def clear_plan(db: Session, row: ContainerLoading, user: User, request) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    row.plan_json = None
    row.plan_filename = None
    row.check_json = None
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = user.id
    db.flush()
    after = snapshot(row, FIELDS)
    write_audit(
        db,
        actor_user_id=user.id,
        action="clear_plan",
        entity_type=ENTITY,
        entity_id=row.id,
        before=before,
        after=after,
        changed=[{"field": "plan", "old": "attached", "new": "cleared"}],
        request=request,
    )
    db.commit()
    db.refresh(row)
    return {
        "item": loading_out(
            row,
            file_count=counts_for(db, LOADING_ENTITY, [row.id]).get(row.id, 0),
        )
    }
