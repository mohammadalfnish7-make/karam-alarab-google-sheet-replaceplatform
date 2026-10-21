from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audit import history_for, write_audit
from app.cargo_files import (
    counts_for,
    file_out,
    get_file,
    list_files,
    parse_extracted,
    require_cargo,
    restore_file,
    soft_delete_file,
    store_file,
)
from app.constants import ENTITY_TYPES
from app.deps import get_current_user, get_db, require_admin
from app.errors import AppError
from app.models import AirCargo, ExitRecord, SeaCargo, User
from app.present import AIR_FIELDS, EXIT_FIELDS, SEA_FIELDS, cargo_out, exit_out
from app.records import (
    list_cargo,
    list_exit,
    mark_deleted,
    mark_restored,
    require_row,
    save_cargo,
    save_exit,
    visible,
)
from app.schemas import CargoIn, ExitIn
from app.validation import next_sea_shipment

router = APIRouter(tags=["records"])

_CONFIRM = ("confirm_new_customer", "confirm_new_company", "confirm_new_supplier")


def _confirms(body) -> dict:
    return {key: getattr(body, key) for key in _CONFIRM}


def _data(body, *, partial: bool) -> dict:
    raw = body.model_dump(exclude_unset=True) if partial else body.model_dump()
    return {key: value for key, value in raw.items() if key not in _CONFIRM}


def register_cargo(kind: str) -> None:
    model = SeaCargo if kind == "sea" else AirCargo
    fields = SEA_FIELDS if kind == "sea" else AIR_FIELDS
    entity = ENTITY_TYPES[kind]

    @router.get(f"/{kind}", operation_id=f"list_{kind}")
    def list_items(
        q: str | None = None,
        needs_review: bool | None = None,
        stage: str | None = None,
        shipping_route: str | None = None,
        status: str | None = None,
        include_deleted: bool = False,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return list_cargo(
            db,
            kind,
            q=q,
            needs_review=needs_review,
            stage=stage,
            shipping_route=shipping_route,
            status=status,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
            user=user,
        )

    @router.post(f"/{kind}", operation_id=f"create_{kind}")
    def create_item(
        body: CargoIn,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return save_cargo(db, kind, _data(body, partial=False), _confirms(body), user, request)

    @router.get(f"/{kind}/{{item_id}}", operation_id=f"get_{kind}")
    def get_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        row = visible(db.get(model, item_id), user)
        counts = counts_for(db, entity, [row.id])
        return cargo_out(row, kind, file_count=counts.get(row.id, 0))

    @router.patch(f"/{kind}/{{item_id}}", operation_id=f"update_{kind}")
    def update_item(
        item_id: int,
        body: CargoIn,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        row = visible(db.get(model, item_id), user)
        return save_cargo(db, kind, _data(body, partial=True), _confirms(body), user, request, row)

    @router.delete(f"/{kind}/{{item_id}}", operation_id=f"delete_{kind}")
    def delete_item(
        item_id: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        row = visible(db.get(model, item_id), user)
        mark_deleted(db, row, user, request, entity, fields)
        return {"ok": True}

    @router.post(f"/{kind}/{{item_id}}/restore", operation_id=f"restore_{kind}")
    def restore_item(
        item_id: int,
        request: Request,
        user: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        row = require_row(db.get(model, item_id))
        mark_restored(db, row, user, request, entity, fields)
        return {"item": cargo_out(row, kind)}

    @router.get(f"/{kind}/{{item_id}}/history", operation_id=f"history_{kind}")
    def history(item_id: int, _user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        require_row(db.get(model, item_id))
        return history_for(db, entity, item_id)

    @router.get(f"/{kind}/{{item_id}}/files", operation_id=f"list_{kind}_files")
    def list_item_files(
        item_id: int,
        include_deleted: bool = False,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_cargo(db, kind, item_id, user)
        show_deleted = include_deleted and user.role == "admin"
        return {"items": list_files(db, entity, item_id, include_deleted=show_deleted)}

    @router.post(f"/{kind}/{{item_id}}/files", operation_id=f"upload_{kind}_files")
    async def upload_item_files(
        item_id: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_cargo(db, kind, item_id, user)
        form = await request.form()
        uploads = [item for item in form.getlist("files") if hasattr(item, "read")]
        kind_tags = [str(value) for value in form.getlist("kinds")]
        labels = [str(value) for value in form.getlist("labels")]
        extracted_list = [str(value) for value in form.getlist("extracted")]
        if not uploads:
            raise AppError(422, {"message": "Upload at least one file"})
        if len(kind_tags) != len(uploads):
            raise AppError(422, {"message": "Each file needs a kind (note, scale, or papers)"})
        stored = []
        for index, upload in enumerate(uploads):
            content = await upload.read()
            label = labels[index] if index < len(labels) else ""
            tag = kind_tags[index]
            if not label:
                if tag == "scale":
                    label = f"Scale {index + 1}"
                elif tag == "papers":
                    label = f"Papers {index + 1}"
                else:
                    label = f"Note {index + 1}"
            raw_extracted = extracted_list[index] if index < len(extracted_list) else None
            row = store_file(
                db,
                entity_type=entity,
                entity_id=item_id,
                kind=tag,
                label=label,
                filename=getattr(upload, "filename", None) or f"file-{index + 1}",
                content=content,
                mime=getattr(upload, "content_type", None),
                extracted=parse_extracted(raw_extracted),
                user=user,
            )
            stored.append(row)
        write_audit(
            db,
            actor_user_id=user.id,
            action="cargo_files_upload",
            entity_type=entity,
            entity_id=item_id,
            before=None,
            after={"files": [{"id": row.id, "kind": row.kind, "filename": row.original_filename} for row in stored]},
            changed=["files"],
            request=request,
        )
        db.commit()
        return {"items": [file_out(row) for row in stored]}

    @router.get(f"/{kind}/{{item_id}}/files/{{file_id}}", operation_id=f"view_{kind}_file")
    def view_item_file(
        item_id: int,
        file_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_cargo(db, kind, item_id, user)
        row = get_file(db, entity, item_id, file_id)
        if row.deleted_at is not None and user.role != "admin":
            raise AppError(404, {"message": "File not found"})
        return FileResponse(
            path=Path(row.stored_path),
            media_type=row.mime,
            filename=row.original_filename,
            content_disposition_type="inline",
        )

    @router.get(f"/{kind}/{{item_id}}/files/{{file_id}}/download", operation_id=f"download_{kind}_file")
    def download_item_file(
        item_id: int,
        file_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_cargo(db, kind, item_id, user)
        row = get_file(db, entity, item_id, file_id)
        if row.deleted_at is not None and user.role != "admin":
            raise AppError(404, {"message": "File not found"})
        return FileResponse(
            path=Path(row.stored_path),
            media_type=row.mime,
            filename=row.original_filename,
            content_disposition_type="attachment",
        )

    @router.delete(f"/{kind}/{{item_id}}/files/{{file_id}}", operation_id=f"delete_{kind}_file")
    def delete_item_file(
        item_id: int,
        file_id: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_cargo(db, kind, item_id, user)
        row = get_file(db, entity, item_id, file_id)
        before = file_out(row)
        soft_delete_file(db, row, user)
        write_audit(
            db,
            actor_user_id=user.id,
            action="cargo_files_delete",
            entity_type=entity,
            entity_id=item_id,
            before=before,
            after=file_out(row),
            changed=["files"],
            request=request,
        )
        db.commit()
        return {"item": file_out(row)}

    @router.post(f"/{kind}/{{item_id}}/files/{{file_id}}/restore", operation_id=f"restore_{kind}_file")
    def restore_item_file(
        item_id: int,
        file_id: int,
        request: Request,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):
        require_cargo(db, kind, item_id, admin)
        row = get_file(db, entity, item_id, file_id)
        before = file_out(row)
        restore_file(db, row)
        after = file_out(row)
        write_audit(
            db,
            actor_user_id=admin.id,
            action="cargo_files_restore",
            entity_type=entity,
            entity_id=item_id,
            before=before,
            after=after,
            changed=["files"],
            request=request,
        )
        db.commit()
        return {"item": after}

    @router.post(f"/{kind}/{{item_id}}/files/{{file_id}}/replace", operation_id=f"replace_{kind}_file")
    async def replace_item_file(
        item_id: int,
        file_id: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Soft-delete the current file and upload a replacement in one step."""
        require_cargo(db, kind, item_id, user)
        old = get_file(db, entity, item_id, file_id)
        if old.deleted_at is not None:
            raise AppError(422, {"message": "Cannot replace a deleted file"})
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise AppError(422, {"message": "Upload a replacement file"})
        content = await upload.read()
        before = file_out(old)
        soft_delete_file(db, old, user)
        new_row = store_file(
            db,
            entity_type=entity,
            entity_id=item_id,
            kind=old.kind,
            label=old.label,
            filename=getattr(upload, "filename", None) or old.original_filename,
            content=content,
            mime=getattr(upload, "content_type", None),
            extracted=old.extracted_json,
            user=user,
        )
        after = file_out(new_row)
        write_audit(
            db,
            actor_user_id=user.id,
            action="cargo_files_replace",
            entity_type=entity,
            entity_id=item_id,
            before=before,
            after={
                "replaced": before,
                "file": {"id": new_row.id, "kind": new_row.kind, "filename": new_row.original_filename},
            },
            changed=["files"],
            request=request,
        )
        db.commit()
        return {"item": after, "replaced": before}


@router.get("/sea/next-shipment", operation_id="next_sea_shipment")
def next_sea_shipment_route(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return next_sea_shipment(db)


register_cargo("sea")
register_cargo("air")


@router.get("/exit")
def list_exit_rows(
    q: str | None = None,
    needs_review: bool | None = None,
    status: str | None = None,
    include_deleted: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_exit(
        db,
        q=q,
        needs_review=needs_review,
        status=status,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
        user=user,
    )


@router.post("/exit")
def create_exit(
    body: ExitIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return save_exit(db, _data(body, partial=False), _confirms(body), user, request)


@router.get("/exit/{item_id}")
def get_exit(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return exit_out(visible(db.get(ExitRecord, item_id), user))


@router.patch("/exit/{item_id}")
def update_exit(
    item_id: int,
    body: ExitIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = visible(db.get(ExitRecord, item_id), user)
    return save_exit(db, _data(body, partial=True), _confirms(body), user, request, row)


@router.delete("/exit/{item_id}")
def delete_exit(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = visible(db.get(ExitRecord, item_id), user)
    mark_deleted(db, row, user, request, "exit_record", EXIT_FIELDS)
    return {"ok": True}


@router.post("/exit/{item_id}/restore")
def restore_exit(
    item_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = require_row(db.get(ExitRecord, item_id))
    mark_restored(db, row, admin, request, "exit_record", EXIT_FIELDS)
    return {"item": exit_out(row)}


@router.get("/exit/{item_id}/history")
def exit_history(item_id: int, _user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_row(db.get(ExitRecord, item_id))
    return history_for(db, "exit_record", item_id)
