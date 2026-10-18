from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.errors import AppError
from app.models import AgentRun, User
from app.present import agent_run_out

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.get("")
def list_agent_runs(
    agent_name: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    filters = []
    if agent_name:
        filters.append(AgentRun.agent_name == agent_name)
    if status:
        filters.append(AgentRun.status == status)
    count_stmt = select(func.count()).select_from(AgentRun)
    stmt = select(AgentRun, User.email).outerjoin(User, User.id == AgentRun.actor_user_id)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    total = db.scalar(count_stmt) or 0
    rows = db.execute(stmt.order_by(AgentRun.started_at.desc(), AgentRun.id.desc()).offset(offset).limit(limit)).all()
    return {"items": [agent_run_out(row, email) for row, email in rows], "total": total}


@router.get("/{run_id}")
def get_agent_run(
    run_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(AgentRun, User.email).outerjoin(User, User.id == AgentRun.actor_user_id).where(AgentRun.id == run_id)
    ).one_or_none()
    if row is None:
        raise AppError(404, {"message": "Not found"})
    run, email = row
    return agent_run_out(run, email, detail=True)
