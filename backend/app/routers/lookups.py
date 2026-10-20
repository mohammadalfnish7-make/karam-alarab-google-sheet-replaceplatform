from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import AIR_STATUSES, CONTAINER_STAGES, EXIT_STATUSES, SEA_STAGES, SHIPPING_ROUTES
from app.deps import get_current_user, get_db
from app.models import Company, Customer, Supplier, User
from app.records import like_pattern

router = APIRouter(prefix="/lookups", tags=["lookups"])


def _search(column, q: str):
    if not q.strip():
        return None
    return column.ilike(like_pattern(q.strip()), escape="\\")


@router.get("/customers")
def customers(
    q: str = "",
    limit: int = Query(20, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Customer).order_by(Customer.code).limit(limit)
    clause = _search(Customer.code, q)
    if clause is not None:
        stmt = stmt.where(clause)
    rows = db.scalars(stmt).all()
    return [{"id": row.id, "code": row.code} for row in rows]


@router.get("/companies")
def companies(
    q: str = "",
    limit: int = Query(20, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Company).order_by(Company.name).limit(limit)
    clause = _search(Company.name, q)
    if clause is not None:
        stmt = stmt.where(clause)
    rows = db.scalars(stmt).all()
    return [{"id": row.id, "name": row.name} for row in rows]


@router.get("/suppliers")
def suppliers(
    q: str = "",
    limit: int = Query(20, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Supplier).order_by(Supplier.name).limit(limit)
    clause = _search(Supplier.name, q)
    if clause is not None:
        stmt = stmt.where(clause)
    rows = db.scalars(stmt).all()
    return [{"id": row.id, "name": row.name} for row in rows]


@router.get("/users")
def users(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.email)).all()
    return [{"id": row.id, "email": row.email, "role": row.role} for row in rows]


@router.get("/enums")
def enums(_user: User = Depends(get_current_user)):
    return {
        "shipping_routes": SHIPPING_ROUTES,
        "stages": SEA_STAGES,
        "air_statuses": AIR_STATUSES,
        "exit_statuses": EXIT_STATUSES,
        "container_stages": CONTAINER_STAGES,
    }
