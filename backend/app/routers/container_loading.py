from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audit import history_for, write_audit
from app.cargo_files import (
    LOADING_ENTITY,
    counts_for,
    file_out,
    get_file,
    list_files,
    require_loading,
    restore_file,
    soft_delete_file,
    store_file,
)
from app.container_loading import (
    ENTITY,
    clear_plan,
    create_row,
    delete_row,
    get_row,
    list_rows,
    loading_out,
    next_mark,
    restore_row,
    set_plan,
    update_row,
)
from app.container_loading_extract import (
    extract_file,
    require_loading_file,
    run_plan_check,
    update_extracted,
)
from app.container_loading_plan import parse_loading_plan
from app.deps import get_current_user, get_db, require_admin
from app.errors import AppError
from app.models import User
from app.schemas import ContainerLoadingIn

router = APIRouter(prefix="/container-loading", tags=["container-loading"])


@router.get("/next-mark")
def get_next_mark(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"mark": next_mark(db)}


@router.get("")
def list_items(
    q: str | None = None,
    include_deleted: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_rows(
        db,
        q=q,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
        user=user,
    )


@router.post("")
def create_item(
    body: ContainerLoadingIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_row(db, body.model_dump(exclude_unset=True), user, request)


@router.get("/{item_id}")
def get_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return {
        "item": loading_out(
            row,
            file_count=counts_for(db, LOADING_ENTITY, [row.id]).get(row.id, 0),
        )
    }


@router.post("/{item_id}/plan")
async def upload_plan(
    item_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    content = await file.read()
    if not content:
        raise AppError(422, {"message": "Empty plan file"})
    name = file.filename or "loading-plan.xlsx"
    if not name.lower().endswith((".xlsx", ".xlsm")):
        raise AppError(422, {"message": "Upload an .xlsx loading plan"})
    plan = parse_loading_plan(content, filename=name)
    return set_plan(db, row, plan, filename=name, user=user, request=request)


@router.delete("/{item_id}/plan")
def remove_plan(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return clear_plan(db, row, user, request)


@router.post("/{item_id}/summarize")
def summarize_item(
    item_id: int,
    request: Request,
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return run_plan_check(db, row, user, request, force=force)


@router.patch("/{item_id}")
def update_item(
    item_id: int,
    body: ContainerLoadingIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return update_row(db, row, body.model_dump(exclude_unset=True), user, request)


@router.delete("/{item_id}")
def remove_item(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return delete_row(db, item_id, user, request)


@router.post("/{item_id}/restore")
def restore_item(
    item_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return restore_row(db, item_id, admin, request)


@router.get("/{item_id}/history")
def item_history(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_row(db, item_id, user)
    return history_for(db, ENTITY, item_id)


@router.get("/{item_id}/files")
def list_item_files(
    item_id: int,
    include_deleted: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_loading(db, item_id, user)
    show_deleted = include_deleted and user.role == "admin"
    return {"items": list_files(db, LOADING_ENTITY, item_id, include_deleted=show_deleted)}


@router.post("/{item_id}/files")
async def upload_item_files(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_loading(db, item_id, user)
    form = await request.form()
    uploads = [item for item in form.getlist("files") if hasattr(item, "read")]
    if not uploads:
        raise AppError(422, {"message": "Upload at least one file"})
    labels = [str(value) for value in form.getlist("labels")]
    stored = []
    for index, upload in enumerate(uploads):
        content = await upload.read()
        label = labels[index] if index < len(labels) else ""
        if not label:
            label = f"Loading {index + 1}"
        row = store_file(
            db,
            entity_type=LOADING_ENTITY,
            entity_id=item_id,
            kind="loading",
            label=label,
            filename=getattr(upload, "filename", None) or f"loading-{index + 1}",
            content=content,
            mime=getattr(upload, "content_type", None),
            extracted=None,
            user=user,
        )
        stored.append(row)
    file_summaries = [
        {"id": row.id, "filename": row.original_filename, "label": row.label}
        for row in stored
    ]
    write_audit(
        db,
        actor_user_id=user.id,
        action="upload_photo",
        entity_type=ENTITY,
        entity_id=item_id,
        before=None,
        after={"photos": file_summaries},
        changed=[
            {
                "field": "photos",
                "old": None,
                "new": ", ".join(item["filename"] for item in file_summaries),
            }
        ],
        request=request,
    )
    db.commit()
    return {"items": [file_out(row) for row in stored]}


@router.get("/{item_id}/files/{file_id}")
def view_item_file(
    item_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_loading(db, item_id, user)
    row = get_file(db, LOADING_ENTITY, item_id, file_id)
    if row.deleted_at is not None and user.role != "admin":
        raise AppError(404, {"message": "File not found"})
    return FileResponse(
        path=Path(row.stored_path),
        media_type=row.mime,
        filename=row.original_filename,
        content_disposition_type="inline",
    )


@router.delete("/{item_id}/files/{file_id}")
def delete_item_file(
    item_id: int,
    file_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_loading(db, item_id, user)
    row = get_file(db, LOADING_ENTITY, item_id, file_id)
    before = file_out(row)
    soft_delete_file(db, row, user)
    write_audit(
        db,
        actor_user_id=user.id,
        action="delete_photo",
        entity_type=ENTITY,
        entity_id=item_id,
        before=before,
        after=file_out(row),
        changed=[
            {
                "field": "photos",
                "old": before.get("file_name") or before.get("label"),
                "new": "deleted",
            }
        ],
        request=request,
    )
    db.commit()
    return {"item": file_out(row)}


@router.post("/{item_id}/files/{file_id}/restore")
def restore_item_file(
    item_id: int,
    file_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    require_loading(db, item_id, admin)
    row = get_file(db, LOADING_ENTITY, item_id, file_id)
    before = file_out(row)
    restore_file(db, row)
    after = file_out(row)
    write_audit(
        db,
        actor_user_id=admin.id,
        action="restore_photo",
        entity_type=ENTITY,
        entity_id=item_id,
        before=before,
        after=after,
        changed=[
            {
                "field": "photos",
                "old": "deleted",
                "new": after.get("file_name") or after.get("label"),
            }
        ],
        request=request,
    )
    db.commit()
    return {"item": after}


@router.post("/{item_id}/files/{file_id}/extract")
def extract_item_file(
    item_id: int,
    file_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    loading, file_row = require_loading_file(db, item_id, file_id, user)
    if loading.deleted_at is not None:
        raise AppError(400, {"message": "Cannot extract on a deleted row"})
    return extract_file(db, loading, file_row, user, request)


@router.patch("/{item_id}/files/{file_id}/extracted")
async def patch_item_extracted(
    item_id: int,
    file_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    loading, file_row = require_loading_file(db, item_id, file_id, user)
    body = await request.json()
    if not isinstance(body, dict):
        raise AppError(422, {"message": "Body must be a JSON object"})
    return update_extracted(db, loading, file_row, body, user, request)
