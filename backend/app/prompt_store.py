"""Load, save, and roll back versioned prompts and simple app settings."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.errors import AppError
from app.models import AppSetting, PromptKey, PromptVersion, User
from app.prompt_defaults import APP_SETTING_KEYS, PROMPT_CATALOG


def ensure_prompts_seeded(db: Session) -> None:
    for key, (label, body) in PROMPT_CATALOG.items():
        row = db.get(PromptKey, key)
        if row is None:
            row = PromptKey(key=key, label=label, active_version_id=None)
            db.add(row)
            db.flush()
        has_version = db.scalar(
            select(func.count()).select_from(PromptVersion).where(PromptVersion.prompt_key == key)
        )
        if not has_version:
            version = PromptVersion(
                prompt_key=key,
                version=1,
                body=body,
                note="Seeded default",
                created_by_user_id=None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(version)
            db.flush()
            row.active_version_id = version.id
            continue
        # Keep loading-photo prompt on the latest catalog default when still an older built-in.
        if key == "container_loading.photo" and row.active_version_id is not None:
            active = db.get(PromptVersion, row.active_version_id)
            marker = "black handwritten DETAIL LINE"
            if active and marker not in (active.body or "") and marker in body:
                next_ver = (
                    db.scalar(
                        select(func.max(PromptVersion.version)).where(PromptVersion.prompt_key == key)
                    )
                    or 0
                ) + 1
                version = PromptVersion(
                    prompt_key=key,
                    version=next_ver,
                    body=body,
                    note="Auto-upgrade: black detail line → name/weight/cartons",
                    created_by_user_id=None,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(version)
                db.flush()
                row.active_version_id = version.id
                row.label = label
    db.flush()


def get_active_prompt(key: str, db: Session | None = None) -> str:
    if key not in PROMPT_CATALOG:
        raise AppError(404, {"message": f"Unknown prompt key: {key}"})
    own = db is None
    session = db or SessionLocal()
    try:
        ensure_prompts_seeded(session)
        row = session.get(PromptKey, key)
        if row is None or row.active_version_id is None:
            return PROMPT_CATALOG[key][1]
        version = session.get(PromptVersion, row.active_version_id)
        if version is None:
            return PROMPT_CATALOG[key][1]
        if own:
            session.commit()
        return version.body
    finally:
        if own:
            session.close()


def list_prompt_summaries(db: Session) -> list[dict]:
    ensure_prompts_seeded(db)
    out: list[dict] = []
    for key, (label, _) in PROMPT_CATALOG.items():
        row = db.get(PromptKey, key)
        active = db.get(PromptVersion, row.active_version_id) if row and row.active_version_id else None
        latest = db.scalar(
            select(func.max(PromptVersion.version)).where(PromptVersion.prompt_key == key)
        )
        out.append(
            {
                "key": key,
                "label": label,
                "active_version": active.version if active else None,
                "latest_version": latest,
                "body": active.body if active else PROMPT_CATALOG[key][1],
                "updated_at": active.created_at.isoformat() if active and active.created_at else None,
            }
        )
    return out


def list_prompt_versions(db: Session, key: str) -> dict:
    if key not in PROMPT_CATALOG:
        raise AppError(404, {"message": f"Unknown prompt key: {key}"})
    ensure_prompts_seeded(db)
    row = db.get(PromptKey, key)
    versions = db.scalars(
        select(PromptVersion)
        .where(PromptVersion.prompt_key == key)
        .order_by(PromptVersion.version.desc())
    ).all()
    user_ids = {v.created_by_user_id for v in versions if v.created_by_user_id}
    emails = {}
    if user_ids:
        for user in db.scalars(select(User).where(User.id.in_(user_ids))).all():
            emails[user.id] = user.email
    return {
        "key": key,
        "label": PROMPT_CATALOG[key][0],
        "active_version": next(
            (v.version for v in versions if row and v.id == row.active_version_id),
            None,
        ),
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "body": v.body,
                "note": v.note,
                "created_by_user_id": v.created_by_user_id,
                "created_by_email": emails.get(v.created_by_user_id) if v.created_by_user_id else None,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "is_active": bool(row and v.id == row.active_version_id),
            }
            for v in versions
        ],
    }


def save_prompt(
    db: Session,
    key: str,
    body: str,
    *,
    note: str | None,
    actor_user_id: int | None,
) -> dict:
    if key not in PROMPT_CATALOG:
        raise AppError(404, {"message": f"Unknown prompt key: {key}"})
    text = (body or "").strip()
    if not text:
        raise AppError(422, {"field_errors": {"body": "Prompt body is required"}, "warnings": []})
    ensure_prompts_seeded(db)
    row = db.get(PromptKey, key)
    assert row is not None
    next_version = (
        db.scalar(select(func.max(PromptVersion.version)).where(PromptVersion.prompt_key == key)) or 0
    ) + 1
    version = PromptVersion(
        prompt_key=key,
        version=next_version,
        body=text,
        note=(note or "").strip() or None,
        created_by_user_id=actor_user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(version)
    db.flush()
    before = row.active_version_id
    row.active_version_id = version.id
    return {
        "key": key,
        "version": version.version,
        "body": version.body,
        "note": version.note,
        "before_active_version_id": before,
        "active_version_id": version.id,
    }


def rollback_prompt(db: Session, key: str, version: int) -> dict:
    if key not in PROMPT_CATALOG:
        raise AppError(404, {"message": f"Unknown prompt key: {key}"})
    ensure_prompts_seeded(db)
    row = db.get(PromptKey, key)
    assert row is not None
    target = db.scalar(
        select(PromptVersion).where(PromptVersion.prompt_key == key, PromptVersion.version == version)
    )
    if target is None:
        raise AppError(404, {"message": f"Version {version} not found for {key}"})
    before_id = row.active_version_id
    before = db.get(PromptVersion, before_id) if before_id else None
    row.active_version_id = target.id
    return {
        "key": key,
        "version": target.version,
        "body": target.body,
        "before_version": before.version if before else None,
        "active_version_id": target.id,
    }


def get_app_settings(db: Session | None = None) -> dict[str, str]:
    own = db is None
    session = db or SessionLocal()
    try:
        rows = {
            row.key: row.value
            for row in session.scalars(select(AppSetting).where(AppSetting.key.in_(APP_SETTING_KEYS))).all()
        }
        return {
            "llm_model": rows.get("llm_model") or (settings.llm_model or "").strip() or "claude-haiku-5-5",
            "llm_timeout_sec": rows.get("llm_timeout_sec") or str(settings.llm_timeout_sec),
        }
    finally:
        if own:
            session.close()


def set_app_settings(
    db: Session,
    updates: dict[str, str | int],
    *,
    actor_user_id: int | None,
) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    errors: dict[str, str] = {}
    if "llm_model" in updates:
        model = str(updates["llm_model"] or "").strip()
        if not model:
            errors["llm_model"] = "Model is required"
        else:
            cleaned["llm_model"] = model
    if "llm_timeout_sec" in updates:
        raw = updates["llm_timeout_sec"]
        try:
            timeout = int(raw)
        except (TypeError, ValueError):
            errors["llm_timeout_sec"] = "Timeout must be an integer"
            timeout = 0
        if "llm_timeout_sec" not in errors and (timeout < 10 or timeout > 600):
            errors["llm_timeout_sec"] = "Timeout must be between 10 and 600 seconds"
        elif "llm_timeout_sec" not in errors:
            cleaned["llm_timeout_sec"] = str(timeout)
    if errors:
        raise AppError(422, {"field_errors": errors, "warnings": []})
    now = datetime.now(timezone.utc)
    for key, value in cleaned.items():
        row = db.get(AppSetting, key)
        if row is None:
            db.add(
                AppSetting(
                    key=key,
                    value=value,
                    updated_at=now,
                    updated_by_user_id=actor_user_id,
                )
            )
        else:
            row.value = value
            row.updated_at = now
            row.updated_by_user_id = actor_user_id
    db.flush()
    return get_app_settings(db)


def llm_model() -> str:
    return get_app_settings()["llm_model"]


def llm_timeout_sec() -> int:
    try:
        return int(get_app_settings()["llm_timeout_sec"])
    except (TypeError, ValueError):
        return settings.llm_timeout_sec
