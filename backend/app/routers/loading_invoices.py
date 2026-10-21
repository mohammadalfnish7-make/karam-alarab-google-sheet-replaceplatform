from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.audit import history_for
from app.deps import get_current_user, get_db, require_admin
from app.errors import AppError
from app.invoice_parse import parse_invoice
from app.loading_invoices import (
    ENTITY,
    create_row,
    delete_row,
    get_row,
    invoice_out,
    list_rows,
    restore_row,
    save_invoice,
    set_invoice_file,
    update_header,
)
from app.models import User
from app.schemas import LoadingInvoiceIn, LoadingInvoicePut

router = APIRouter(prefix="/loading-invoices", tags=["loading-invoices"])


@router.get("")
def list_items(
    q: str | None = None,
    include_deleted: bool = False,
    container_loading_id: int | None = None,
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
        container_loading_id=container_loading_id,
    )


@router.post("")
def create_item(
    body: LoadingInvoiceIn,
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
    from app.loading_invoices import _attach_loading_marks

    _attach_loading_marks(db, [row])
    return {"item": invoice_out(row)}


@router.patch("/{item_id}")
def patch_item(
    item_id: int,
    body: LoadingInvoiceIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return update_header(db, row, body.model_dump(exclude_unset=True), user, request)


@router.put("/{item_id}")
def put_item(
    item_id: int,
    body: LoadingInvoicePut,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return save_invoice(db, row, body.model_dump(), user, request)


@router.post("/{item_id}/file")
async def upload_file(
    item_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    content = await file.read()
    if not content:
        raise AppError(422, {"message": "Empty invoice file"})
    name = file.filename or "invoice.xlsx"
    if not name.lower().endswith((".xlsx", ".xlsm")):
        raise AppError(422, {"message": "Upload an .xlsx invoice"})
    plan = parse_invoice(content, filename=name)
    return set_invoice_file(db, row, plan, filename=name, user=user, request=request)


@router.delete("/{item_id}")
def remove_item(
    item_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return delete_row(db, row, user, request)


@router.post("/{item_id}/restore")
def restore_item(
    item_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return restore_row(db, row, user, request)


@router.get("/{item_id}/history")
def history(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_row(db, item_id, user)
    return history_for(db, ENTITY, row.id)
