from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_admin
from app.models import User
from app.overview import dashboard_summary, list_shipments

router = APIRouter(tags=["overview"])


@router.get("/dashboard")
def dashboard(_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return dashboard_summary(db)


@router.get("/shipments")
def shipments(
    q: str | None = None,
    kind: str | None = None,
    progress: str | None = None,
    needs_review: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_shipments(
        db,
        q=q,
        kind=kind,
        progress=progress,
        needs_review=needs_review,
        limit=limit,
        offset=offset,
    )
