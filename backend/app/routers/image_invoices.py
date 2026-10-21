from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.audit import history_for, write_audit
from app.cargo_files import (
    IMAGE_INVOICE_LINE_ENTITY,
    file_out,
    get_file,
    list_files,
    require_image_invoice_line,
    restore_file,
    soft_delete_file,
    store_file,
)
from app.deps import get_current_user, get_db, require_admin
from app.errors import AppError
from app.image_invoice_export import export_payload
from app.image_invoice_extract import extract_line
from app.image_invoices import (
    ENTITY,
    add_line,
    create_row,
    delete_line,
    delete_row,
    get_detail,
    get_invoice,
    get_line,
    list_rows,
    restore_row,
    save_lines,
    update_header,
)
from app.models import User
from app.schemas import (
    ImageInvoiceExportIn,
    ImageInvoiceExtractIn,
    ImageInvoiceIn,
    ImageInvoiceLinesPut,
)

router = APIRouter(prefix="/image-invoices", tags=["image-invoices"])


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
    body: ImageInvoiceIn,
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
    row = get_invoice(db, item_id, user)
    return get_detail(db, row)


@router.patch("/{item_id}")
def patch_item(
    item_id: int,
    body: ImageInvoiceIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    return update_header(db, row, body.model_dump(exclude_unset=True), user, request)


@router.put("/{item_id}/lines")
def put_lines(
    item_id: int,
    body: ImageInvoiceLinesPut,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    return save_lines(db, row, body.model_dump(), user, request)


@router.post("/{item_id}/lines")
def create_line(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    return add_line(db, row, user, request)


@router.delete("/{item_id}/lines/{line_id}")
def remove_line(
    item_id: int,
    line_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    line = get_line(db, item_id, line_id, user)
    return delete_line(db, row, line, user, request)


@router.get("/{item_id}/export")
def export_item(
    item_id: int,
    filename: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    content, name = export_payload(db, row, filename=filename)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
        },
    )


@router.post("/{item_id}/export")
def export_item_post(
    item_id: int,
    body: ImageInvoiceExportIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    opts = body or ImageInvoiceExportIn()
    raw_name = opts.filename
    content, name = export_payload(
        db,
        row,
        filename=None if raw_name is None else str(raw_name),
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
        },
    )


@router.post("/{item_id}/lines/{line_id}/extract")
def extract_item_line(
    item_id: int,
    line_id: int,
    request: Request,
    body: ImageInvoiceExtractIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    line = get_line(db, item_id, line_id, user)
    opts = body or ImageInvoiceExtractIn()
    return extract_line(
        db,
        row,
        line,
        user,
        request,
        overwrite=opts.overwrite,
        file_ids=opts.file_ids,
    )


@router.get("/{item_id}/lines/{line_id}/files")
def list_line_files(
    item_id: int,
    line_id: int,
    include_deleted: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_line(db, item_id, line_id, user)
    show_deleted = include_deleted and user.role == "admin"
    return {
        "items": list_files(
            db,
            IMAGE_INVOICE_LINE_ENTITY,
            line_id,
            include_deleted=show_deleted,
        )
    }


@router.post("/{item_id}/lines/{line_id}/files")
async def upload_line_files(
    item_id: int,
    line_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_line(db, item_id, line_id, user)
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
            label = f"Product {index + 1}"
        row = store_file(
            db,
            entity_type=IMAGE_INVOICE_LINE_ENTITY,
            entity_id=line_id,
            kind="product",
            label=label,
            filename=getattr(upload, "filename", None) or f"product-{index + 1}",
            content=content,
            mime=getattr(upload, "content_type", None),
            extracted=None,
            user=user,
        )
        stored.append(row)
    write_audit(
        db,
        actor_user_id=user.id,
        action="upload_photo",
        entity_type=ENTITY,
        entity_id=item_id,
        before=None,
        after={"files": [{"id": row.id, "filename": row.original_filename} for row in stored]},
        changed=["files"],
        request=request,
    )
    db.commit()
    return {"items": [file_out(row) for row in stored]}


@router.get("/{item_id}/lines/{line_id}/files/{file_id}")
def view_line_file(
    item_id: int,
    line_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_line(db, item_id, line_id, user)
    require_image_invoice_line(db, line_id, user)
    row = get_file(db, IMAGE_INVOICE_LINE_ENTITY, line_id, file_id)
    if row.deleted_at is not None and user.role != "admin":
        raise AppError(404, {"message": "File not found"})
    return FileResponse(
        path=Path(row.stored_path),
        media_type=row.mime,
        filename=row.original_filename,
        content_disposition_type="inline",
    )


@router.delete("/{item_id}/lines/{line_id}/files/{file_id}")
def delete_line_file(
    item_id: int,
    line_id: int,
    file_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_line(db, item_id, line_id, user)
    row = get_file(db, IMAGE_INVOICE_LINE_ENTITY, line_id, file_id)
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
        changed=["files"],
        request=request,
    )
    db.commit()
    return {"item": file_out(row)}


@router.post("/{item_id}/lines/{line_id}/files/{file_id}/restore")
def restore_line_file(
    item_id: int,
    line_id: int,
    file_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    get_line(db, item_id, line_id, admin)
    row = get_file(db, IMAGE_INVOICE_LINE_ENTITY, line_id, file_id)
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
        changed=["files"],
        request=request,
    )
    db.commit()
    return {"item": after}


@router.delete("/{item_id}")
def remove_item(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    return delete_row(db, row, user, request)


@router.post("/{item_id}/restore")
def restore_item(
    item_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, admin)
    return restore_row(db, row, admin, request)


@router.get("/{item_id}/history")
def history(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_invoice(db, item_id, user)
    return history_for(db, ENTITY, row.id)
