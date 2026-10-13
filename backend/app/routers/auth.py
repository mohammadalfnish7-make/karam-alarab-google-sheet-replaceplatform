from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.config import settings
from app.deps import get_current_user, get_db
from app.errors import AppError
from app.models import User
from app.present import user_out
from app.schemas import LoginIn
from app.security import create_token, read_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_exp_hours * 3600,
        path="/",
    )


def _clear_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        write_audit(
            db,
            actor_user_id=user.id if user else None,
            action="login_failed",
            entity_type="session",
            entity_id=user.id if user else None,
            before=None,
            after={"email": email},
            changed=[],
            request=request,
        )
        db.commit()
        raise AppError(401, {"message": "Invalid email or password"})
    if not user.is_active:
        write_audit(
            db,
            actor_user_id=user.id,
            action="login_failed",
            entity_type="session",
            entity_id=user.id,
            before=None,
            after={"email": email},
            changed=[],
            request=request,
        )
        db.commit()
        raise AppError(401, {"message": "Account disabled"})
    write_audit(
        db,
        actor_user_id=user.id,
        action="login",
        entity_type="session",
        entity_id=user.id,
        before=None,
        after={"email": user.email},
        changed=[],
        request=request,
    )
    db.commit()
    response = JSONResponse(user_out(user))
    _set_cookie(response, create_token(user.id))
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user_id = read_token(token) if token else None
    user = db.get(User, user_id) if user_id is not None else None
    if user is not None and user.is_active:
        write_audit(
            db,
            actor_user_id=user.id,
            action="logout",
            entity_type="session",
            entity_id=user.id,
            before=None,
            after={"email": user.email},
            changed=[],
            request=request,
        )
        db.commit()
    response = JSONResponse({"ok": True})
    _clear_cookie(response)
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)
