from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.deps import get_db, require_admin
from app.models import User
from app.prompt_store import (
    get_app_settings,
    list_prompt_summaries,
    list_prompt_versions,
    rollback_prompt,
    save_prompt,
    set_app_settings,
)
from app.schemas import AppSettingsIn, PromptRollbackIn, PromptUpdateIn

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    prompts = list_prompt_summaries(db)
    app = get_app_settings(db)
    db.commit()
    return {"prompts": prompts, "app": app}


@router.get("/prompts/{key}")
def get_prompt(key: str, _admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = list_prompt_versions(db, key)
    db.commit()
    return result


@router.put("/prompts/{key}")
def update_prompt(
    key: str,
    body: PromptUpdateIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    before = list_prompt_versions(db, key)
    before_active = next((row for row in before["versions"] if row["is_active"]), None)
    result = save_prompt(db, key, body.body, note=body.note, actor_user_id=admin.id)
    write_audit(
        db,
        actor_user_id=admin.id,
        action="prompt.update",
        entity_type="prompt",
        entity_id=key,
        before={
            "active_version": before.get("active_version"),
            "body": before_active["body"] if before_active else None,
        },
        after={"active_version": result["version"], "body": result["body"], "note": result["note"]},
        changed=[{"field": "active_version", "old": before.get("active_version"), "new": result["version"]}],
        request=request,
    )
    db.commit()
    return list_prompt_versions(db, key)


@router.post("/prompts/{key}/rollback")
def rollback_prompt_version(
    key: str,
    body: PromptRollbackIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    result = rollback_prompt(db, key, body.version)
    write_audit(
        db,
        actor_user_id=admin.id,
        action="prompt.rollback",
        entity_type="prompt",
        entity_id=key,
        before={"active_version": result["before_version"]},
        after={"active_version": result["version"], "body": result["body"]},
        changed=[{"field": "active_version", "old": result["before_version"], "new": result["version"]}],
        request=request,
    )
    db.commit()
    return list_prompt_versions(db, key)


@router.put("/app")
def update_app_settings(
    body: AppSettingsIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    before = get_app_settings(db)
    updates = {}
    if body.llm_model is not None:
        updates["llm_model"] = body.llm_model
    if body.llm_timeout_sec is not None:
        updates["llm_timeout_sec"] = body.llm_timeout_sec
    after = set_app_settings(db, updates, actor_user_id=admin.id) if updates else before
    changed = [
        {"field": key, "old": before.get(key), "new": after.get(key)}
        for key in after
        if before.get(key) != after.get(key)
    ]
    if changed:
        write_audit(
            db,
            actor_user_id=admin.id,
            action="settings.update",
            entity_type="app_settings",
            entity_id="app",
            before=before,
            after=after,
            changed=changed,
            request=request,
        )
    db.commit()
    return {"app": after}
