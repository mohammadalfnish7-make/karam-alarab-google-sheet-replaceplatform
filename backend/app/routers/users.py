import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.deps import get_db, require_admin
from app.errors import AppError
from app.models import User
from app.present import user_out
from app.schemas import UserCreate, UserPatch
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.get("")
def list_users(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.email)).all()
    return [user_out(row) for row in rows]


@router.post("")
def create_user(
    body: UserCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email = body.email.strip().lower()
    errors = {}
    if not _EMAIL.fullmatch(email):
        errors["email"] = "Enter a valid email"
    if len(body.password) < 8:
        errors["password"] = "Password must be at least 8 characters"
    if body.role not in {"admin", "operator"}:
        errors["role"] = "Role must be admin or operator"
    if errors:
        raise AppError(422, {"field_errors": errors, "warnings": []})
    if db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, {"message": "Email already exists"})
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    write_audit(
        db,
        actor_user_id=admin.id,
        action="create",
        entity_type="user",
        entity_id=user.id,
        before=None,
        after={"email": user.email, "role": user.role, "is_active": True},
        changed=[
            {"field": "email", "old": None, "new": user.email},
            {"field": "role", "old": None, "new": user.role},
        ],
        request=request,
    )
    db.commit()
    return user_out(user)


@router.patch("/{user_id}")
def patch_user(
    user_id: int,
    body: UserPatch,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, {"message": "Not found"})
    if user.id == admin.id and body.is_active is False:
        raise AppError(400, {"message": "You cannot disable your own account"})
    if body.is_active is False and user.role == "admin" and user.is_active:
        others = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == "admin", User.is_active.is_(True), User.id != user.id)
        )
        if not others:
            raise AppError(400, {"message": "Cannot disable the last active admin"})
    before = user.is_active
    user.is_active = body.is_active
    write_audit(
        db,
        actor_user_id=admin.id,
        action="update",
        entity_type="user",
        entity_id=user.id,
        before={"is_active": before},
        after={"email": user.email, "role": user.role, "is_active": user.is_active},
        changed=[{"field": "is_active", "old": before, "new": user.is_active}] if before != user.is_active else [],
        request=request,
    )
    db.commit()
    return user_out(user)
