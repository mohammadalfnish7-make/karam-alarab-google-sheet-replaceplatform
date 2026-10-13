from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.errors import AppError
from app.models import User
from app.security import read_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise AppError(401, {"message": "Not authenticated"})
    user_id = read_token(token)
    if user_id is None:
        raise AppError(401, {"message": "Not authenticated"})
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, {"message": "Not authenticated"})
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AppError(403, {"message": "Admin only"})
    return user
