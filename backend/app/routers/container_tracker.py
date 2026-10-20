from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audit import history_for, write_audit
from app.cargo_files import (
    CONTAINER_ENTITY,
    file_out,
    get_file,
    list_files,
    require_container,
    restore_file,
    soft_delete_file,
    store_file,
)
from app.container_tracker import (
    SHEETS,
    delete_row,
    get_row,
    list_sheet,
    restore_row,
    save_sheet,
    sheet_out,
)
from app.deps import get_current_user, get_db, require_admin
from app.errors import AppError
from app.models import User
from app.records import require_row
from app.schemas import SheetRowIn

router = APIRouter(tags=["container-tracker"])


def _mount(kind: str, prefix: str, slug: str) -> None:
    cfg = SHEETS[kind]

    def list_items(
        q: str | None = None,
        needs_review: bool | None = None,
        include_deleted: bool = False,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return list_sheet(
            db,
            kind,
            q=q,
            needs_review=needs_review,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
            user=user,
        )

    def create_item(
        body: SheetRowIn,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return save_sheet(db, kind, body.model_dump(exclude_unset=True), user, request)

    def get_item(
        item_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return sheet_out(kind, get_row(db, kind, item_id, user))

    def update_item(
        item_id: int,
        body: SheetRowIn,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        row = get_row(db, kind, item_id, user)
        return save_sheet(db, kind, body.model_dump(exclude_unset=True), user, request, row)

    def remove_item(
        item_id: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return delete_row(db, kind, item_id, user, request)

    def restore_item(
        item_id: int,
        request: Request,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        return restore_row(db, kind, item_id, admin, request)

    def item_history(
        item_id: int,
        _user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_row(db.get(cfg["model"], item_id))
        return history_for(db, cfg["entity_type"], item_id)

    list_items.__name__ = f"list_{slug}"
    create_item.__name__ = f"create_{slug}"
    get_item.__name__ = f"get_{slug}"
    update_item.__name__ = f"update_{slug}"
    remove_item.__name__ = f"delete_{slug}"
    restore_item.__name__ = f"restore_{slug}"
    item_history.__name__ = f"history_{slug}"

    router.add_api_route(prefix, list_items, methods=["GET"])
    router.add_api_route(prefix, create_item, methods=["POST"])
    router.add_api_route(f"{prefix}/{{item_id}}", get_item, methods=["GET"])
    router.add_api_route(f"{prefix}/{{item_id}}", update_item, methods=["PATCH"])
    router.add_api_route(f"{prefix}/{{item_id}}", remove_item, methods=["DELETE"])
    router.add_api_route(f"{prefix}/{{item_id}}/restore", restore_item, methods=["POST"])
    router.add_api_route(f"{prefix}/{{item_id}}/history", item_history, methods=["GET"])


_mount("containers", "/containers", "containers")
_mount("air-tracker", "/air-tracker", "air_tracker")
_mount("coo", "/coo", "coo")
_mount("flight-schedule", "/flight-schedule", "flight_schedule")


@router.get("/containers/{item_id}/files")
def list_container_files(
    item_id: int,
    include_deleted: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_container(db, item_id, user)
    show_deleted = include_deleted and user.role == "admin"
    return {"items": list_files(db, CONTAINER_ENTITY, item_id, include_deleted=show_deleted)}


@router.post("/containers/{item_id}/files")
async def upload_container_files(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_container(db, item_id, user)
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
            entity_type=CONTAINER_ENTITY,
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
    write_audit(
        db,
        actor_user_id=user.id,
        action="container_loading_upload",
        entity_type=CONTAINER_ENTITY,
        entity_id=item_id,
        before=None,
        after={"files": [{"id": row.id, "filename": row.original_filename} for row in stored]},
        changed=["files"],
        request=request,
    )
    db.commit()
    return {"items": [file_out(row) for row in stored]}


@router.get("/containers/{item_id}/files/{file_id}")
def view_container_file(
    item_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_container(db, item_id, user)
    row = get_file(db, CONTAINER_ENTITY, item_id, file_id)
    if row.deleted_at is not None and user.role != "admin":
        raise AppError(404, {"message": "File not found"})
    return FileResponse(
        path=Path(row.stored_path),
        media_type=row.mime,
        filename=row.original_filename,
        content_disposition_type="inline",
    )


@router.delete("/containers/{item_id}/files/{file_id}")
def delete_container_file(
    item_id: int,
    file_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_container(db, item_id, user)
    row = get_file(db, CONTAINER_ENTITY, item_id, file_id)
    before = file_out(row)
    soft_delete_file(db, row, user)
    write_audit(
        db,
        actor_user_id=user.id,
        action="container_loading_delete",
        entity_type=CONTAINER_ENTITY,
        entity_id=item_id,
        before=before,
        after=file_out(row),
        changed=["deleted_at"],
        request=request,
    )
    db.commit()
    return {"item": file_out(row)}


@router.post("/containers/{item_id}/files/{file_id}/restore")
def restore_container_file(
    item_id: int,
    file_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    require_container(db, item_id, admin)
    row = get_file(db, CONTAINER_ENTITY, item_id, file_id)
    before = file_out(row)
    restore_file(db, row)
    write_audit(
        db,
        actor_user_id=admin.id,
        action="container_loading_restore",
        entity_type=CONTAINER_ENTITY,
        entity_id=item_id,
        before=before,
        after=file_out(row),
        changed=["deleted_at"],
        request=request,
    )
    db.commit()
    return {"item": file_out(row)}

