from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import AuditLog, User
from app.present import audit_out

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = []
    if user_id is not None:
        filters.append(AuditLog.actor_user_id == user_id)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id:
        filters.append(AuditLog.entity_id == entity_id)
    if action:
        filters.append(AuditLog.action == action)
    if from_date is not None:
        start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        filters.append(AuditLog.created_at >= start)
    if to_date is not None:
        end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        filters.append(AuditLog.created_at < end)

    count_stmt = select(func.count()).select_from(AuditLog)
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_user_id)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    total = db.scalar(count_stmt) or 0
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)).all()
    return {"items": [audit_out(row, email) for row, email in rows], "total": total}
