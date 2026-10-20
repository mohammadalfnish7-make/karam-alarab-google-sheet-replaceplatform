from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audit import history_for, write_audit
from app.cargo_files import (
    EXPENSE_ENTITY,
    file_out,
    get_file,
    list_files,
    require_expense,
    restore_file,
    soft_delete_file,
    store_file,
)
from app.expense_summarize import summarize_expense
from app.expenses import (
    ENTITY,
    budget,
    create_row,
    delete_row,
    expense_out,
    get_row,
    list_rows,
    next_mark,
    restore_row,
    update_row,
)
from app.deps import get_current_user, get_db, require_admin
from app.errors import AppError
from app.models import User
from app.schemas import ExpenseIn

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("/next-mark")
def get_next_mark(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"mark": next_mark(db)}


@router.get("/budget")
def get_budget(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return budget(db)


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
    body: ExpenseIn,
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
    return {"item": expense_out(row)}


@router.patch("/{item_id}")
def update_item(
    item_id: int,
    body: ExpenseIn,
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


@router.post("/{item_id}/summarize")
def summarize_item(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return summarize_expense(db, row, user, request)


@router.get("/{item_id}/files")
def list_item_files(
    item_id: int,
    include_deleted: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_expense(db, item_id, user)
    show_deleted = include_deleted and user.role == "admin"
    return {"items": list_files(db, EXPENSE_ENTITY, item_id, include_deleted=show_deleted)}


@router.post("/{item_id}/files")
async def upload_item_files(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_expense(db, item_id, user)
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
            label = f"Receipt {index + 1}"
        row = store_file(
            db,
            entity_type=EXPENSE_ENTITY,
            entity_id=item_id,
            kind="receipt",
            label=label,
            filename=getattr(upload, "filename", None) or f"receipt-{index + 1}",
            content=content,
            mime=getattr(upload, "content_type", None),
            extracted=None,
            user=user,
        )
        stored.append(row)
    names = ", ".join(row.original_filename for row in stored)
    write_audit(
        db,
        actor_user_id=user.id,
        action="upload_photo",
        entity_type=ENTITY,
        entity_id=item_id,
        before=None,
        after={"photos": [{"id": row.id, "filename": row.original_filename} for row in stored]},
        changed=[{"field": "photos", "old": None, "new": names}],
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
    require_expense(db, item_id, user)
    row = get_file(db, EXPENSE_ENTITY, item_id, file_id)
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
    require_expense(db, item_id, user)
    row = get_file(db, EXPENSE_ENTITY, item_id, file_id)
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
        changed=[{"field": "photos", "old": before.get("file_name"), "new": "deleted"}],
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
    require_expense(db, item_id, admin)
    row = get_file(db, EXPENSE_ENTITY, item_id, file_id)
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
        changed=[{"field": "photos", "old": "deleted", "new": after.get("file_name")}],
        request=request,
    )
    db.commit()
    return {"item": after}
