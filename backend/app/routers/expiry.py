from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.audit import history_for
from app.deps import get_current_user, get_db
from app.errors import AppError
from app.expiry import (
    ENTITY_TYPE,
    list_expiry,
    parse_expiry_date,
    require_expiry,
    update_expiry_date,
)
from app.models import User
from app.schemas import ExpiryDateIn

router = APIRouter(prefix="/expiry", tags=["expiry"])


@router.get("")
def get_expiry(
    category: str | None = Query(None),
    status: str | None = Query(None),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if category and category not in {"company", "employee", "vehicle"}:
        raise AppError(422, {"message": "Category must be company, employee, or vehicle"})
    if status and status not in {"expired", "urgent", "soon", "ok", "unknown"}:
        raise AppError(422, {"message": "Invalid status filter"})
    return list_expiry(db, category=category, status=status)


@router.patch("/{item_id}")
def patch_expiry(
    item_id: int,
    body: ExpiryDateIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = require_expiry(db, item_id)
    expiry = parse_expiry_date(body.expiry_date)
    return update_expiry_date(db, row, expiry_date=expiry, user=user, request=request)


@router.get("/{item_id}/history")
def expiry_history(
    item_id: int,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_expiry(db, item_id)
    return history_for(db, ENTITY_TYPE, item_id)
