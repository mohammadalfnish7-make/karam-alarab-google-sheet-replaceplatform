from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.security import hash_password


def seed_admin(db: Session) -> bool:
    count = db.scalar(select(func.count()).select_from(User))
    if count:
        return False
    db.add(
        User(
            email=settings.admin_email.strip().lower(),
            password_hash=hash_password(settings.admin_password),
            role="admin",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return True
