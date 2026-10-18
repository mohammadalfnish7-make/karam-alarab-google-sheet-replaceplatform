from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models import RequestLog, User
from app.present import request_log_out

router = APIRouter(prefix="/request-logs", tags=["request-logs"])


@router.get("")
def list_request_logs(
    path: str | None = None,
    status_code: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    filters = []
    if path:
        filters.append(RequestLog.path.contains(path))
    if status_code is not None:
        filters.append(RequestLog.status_code == status_code)
    count_stmt = select(func.count()).select_from(RequestLog)
    stmt = select(RequestLog, User.email).outerjoin(User, User.id == RequestLog.actor_user_id)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        stmt.order_by(RequestLog.created_at.desc(), RequestLog.id.desc()).offset(offset).limit(limit)
    ).all()
    return {"items": [request_log_out(row, email) for row, email in rows], "total": total}
