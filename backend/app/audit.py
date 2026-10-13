from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.present import audit_out


def client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host
    return None


def user_agent(request) -> str | None:
    if request is None:
        return None
    agent = request.headers.get("user-agent")
    if not agent:
        return None
    return agent[:500]


def write_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str | None,
    entity_id: Any,
    before: Any,
    after: Any,
    changed: list | None,
    request,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            before_json=before,
            after_json=after,
            changed_fields=changed or [],
            ip=client_ip(request),
            user_agent=user_agent(request),
            created_at=datetime.now(timezone.utc),
        )
    )


def history_for(db: Session, entity_type: str, entity_id: Any) -> list[dict]:
    stmt = (
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == str(entity_id))
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    )
    return [audit_out(row, email) for row, email in db.execute(stmt).all()]
