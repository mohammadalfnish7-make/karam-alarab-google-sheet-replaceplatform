"""CRUD for loading invoices linked to container loadings."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.errors import AppError
from app.invoice_parse import finalize_invoice_json
from app.models import ContainerLoading, LoadingInvoice, User
from app.present import diff, iso, snapshot
from app.records import mark_deleted, mark_restored

FIELDS = [
    "ref",
    "container_loading_id",
    "container_no",
    "invoice_date",
    "filename",
    "invoice_json",
    "deleted_at",
    "deleted_by",
]
ENTITY = "loading_invoice"


def empty_invoice_json(*, ref: str | None = None, container_no: str | None = None) -> dict[str, Any]:
    return finalize_invoice_json(
        {
            "ref": ref or "NEW",
            "title": None,
            "plate_line": None,
            "coo_line": None,
            "container_no": container_no,
            "invoice_date": None,
            "filename": "manual",
            "lines": [],
        }
    )


def invoice_out(row: LoadingInvoice, *, summary_only: bool = False) -> dict[str, Any]:
    data = row.invoice_json if isinstance(row.invoice_json, dict) else {}
    loading_mark = None
    if row.container_loading_id:
        loading = row.__dict__.get("_loading_mark")
        if loading is None:
            pass
        else:
            loading_mark = loading
    payload = {
        "id": row.id,
        "ref": row.ref,
        "container_loading_id": row.container_loading_id,
        "loading_mark": loading_mark,
        "container_no": row.container_no,
        "invoice_date": iso(row.invoice_date),
        "filename": row.filename,
        "line_count": data.get("line_count") or 0,
        "group_count": data.get("group_count") or 0,
        "total_cartons": data.get("total_cartons"),
        "total_weight": data.get("total_weight"),
        "created_at": iso(row.created_at),
        "created_by": row.created_by,
        "updated_at": iso(row.updated_at),
        "updated_by": row.updated_by,
        "deleted_at": iso(row.deleted_at),
        "deleted_by": row.deleted_by,
    }
    if not summary_only:
        payload["invoice"] = data
    else:
        payload["groups"] = data.get("groups") or []
    return payload


def get_row(db: Session, item_id: int, user: User) -> LoadingInvoice:
    row = db.get(LoadingInvoice, item_id)
    if row is None or (row.deleted_at is not None and user.role != "admin"):
        raise AppError(404, {"message": "Not found"})
    return row


def _attach_loading_marks(db: Session, rows: list[LoadingInvoice]) -> None:
    ids = [row.container_loading_id for row in rows if row.container_loading_id]
    if not ids:
        return
    marks = {
        loading.id: loading.mark
        for loading in db.scalars(
            select(ContainerLoading).where(ContainerLoading.id.in_(ids))
        ).all()
    }
    for row in rows:
        if row.container_loading_id:
            row.__dict__["_loading_mark"] = marks.get(row.container_loading_id)


def _resolve_loading_id(db: Session, raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    try:
        loading_id = int(raw)
    except (TypeError, ValueError):
        raise AppError(422, {"field_errors": {"container_loading_id": "Invalid loading id"}}) from None
    loading = db.get(ContainerLoading, loading_id)
    if loading is None or loading.deleted_at is not None:
        raise AppError(422, {"field_errors": {"container_loading_id": "Loading row not found"}})
    return loading_id


def _parse_date(raw: Any) -> date | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise AppError(422, {"field_errors": {"invoice_date": "Use YYYY-MM-DD"}}) from None


def _normalize_ref(raw: Any, *, required: bool = True) -> str | None:
    ref = str(raw or "").strip()
    if not ref:
        if required:
            raise AppError(422, {"field_errors": {"ref": "Ref is required"}})
        return None
    if len(ref) > 64:
        raise AppError(422, {"field_errors": {"ref": "Ref is too long"}})
    return ref


def normalize_invoice_payload(body: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise AppError(422, {"message": "Invoice body is required"})
    ref = _normalize_ref(body.get("ref"))
    assert ref is not None
    raw_lines = body.get("lines")
    if raw_lines is None:
        raw_lines = []
    if not isinstance(raw_lines, list):
        raise AppError(422, {"field_errors": {"lines": "Lines must be a list"}})

    lines: list[dict[str, Any]] = []
    field_errors: dict[str, str] = {}
    for index, raw in enumerate(raw_lines):
        if not isinstance(raw, dict):
            field_errors[f"lines.{index}"] = "Invalid row"
            continue
        description = str(raw.get("description") or "").strip() or None
        mark = str(raw.get("mark") or "").strip() or None
        shop = str(raw.get("shop") or "").strip() or None
        if not description and not mark and not shop:
            continue
        if not description:
            field_errors[f"lines.{index}.description"] = "Description is required"
            continue
        cartons = raw.get("cartons")
        weight = raw.get("weight")
        pcs = raw.get("pcs")
        try:
            cartons_n = int(cartons) if cartons not in (None, "") else None
        except (TypeError, ValueError):
            field_errors[f"lines.{index}.cartons"] = "Invalid cartons"
            continue
        try:
            weight_n = float(weight) if weight not in (None, "") else None
            if weight_n is not None and weight_n == int(weight_n):
                weight_n = int(weight_n)
        except (TypeError, ValueError):
            field_errors[f"lines.{index}.weight"] = "Invalid weight"
            continue
        try:
            pcs_n = int(pcs) if pcs not in (None, "") else None
        except (TypeError, ValueError):
            field_errors[f"lines.{index}.pcs"] = "Invalid pcs"
            continue
        no = raw.get("no")
        try:
            no_n = int(no) if no not in (None, "") else index + 1
        except (TypeError, ValueError):
            no_n = index + 1
        lines.append(
            {
                "no": no_n,
                "mark": mark,
                "shop": shop,
                "description": description,
                "coo": str(raw.get("coo") or "").strip() or None,
                "pcs": pcs_n,
                "hs_code": str(raw.get("hs_code") or "").strip() or None,
                "type": str(raw.get("type") or "").strip() or None,
                "cartons": cartons_n,
                "weight": weight_n,
            }
        )

    if field_errors:
        raise AppError(422, {"message": "Fix invoice row errors", "field_errors": field_errors})

    container_no = str(body.get("container_no") or "").strip() or None
    coo_line = str(body.get("coo_line") or "").strip() or None
    invoice_date = body.get("invoice_date")
    if invoice_date not in (None, ""):
        parsed = _parse_date(invoice_date)
        invoice_date_s = parsed.isoformat() if parsed else None
    else:
        invoice_date_s = None

    return finalize_invoice_json(
        {
            "ref": ref,
            "title": body.get("title") or f"INVOICE & PAKING LIST :{ref}",
            "plate_line": body.get("plate_line"),
            "coo_line": coo_line,
            "container_no": container_no,
            "invoice_date": invoice_date_s,
            "filename": body.get("filename") or "manual",
            "lines": lines,
        }
    )


def list_rows(
    db: Session,
    *,
    q: str | None,
    include_deleted: bool,
    limit: int,
    offset: int,
    user: User,
    container_loading_id: int | None = None,
) -> dict[str, Any]:
    stmt = select(LoadingInvoice)
    count_stmt = select(func.count()).select_from(LoadingInvoice)
    if not include_deleted or user.role != "admin":
        stmt = stmt.where(LoadingInvoice.deleted_at.is_(None))
        count_stmt = count_stmt.where(LoadingInvoice.deleted_at.is_(None))
    if container_loading_id is not None:
        stmt = stmt.where(LoadingInvoice.container_loading_id == container_loading_id)
        count_stmt = count_stmt.where(LoadingInvoice.container_loading_id == container_loading_id)
    if q:
        like = f"%{q.strip()}%"
        filt = or_(LoadingInvoice.ref.ilike(like), LoadingInvoice.container_no.ilike(like))
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    total = db.scalar(count_stmt) or 0
    rows = list(db.scalars(stmt.order_by(LoadingInvoice.id.desc()).offset(offset).limit(limit)).all())
    _attach_loading_marks(db, rows)
    return {
        "items": [invoice_out(row, summary_only=True) for row in rows],
        "total": total,
    }


def create_row(db: Session, data: dict[str, Any], user: User, request) -> dict[str, Any]:
    ref = _normalize_ref(data.get("ref") or "NEW")
    assert ref is not None
    loading_id = _resolve_loading_id(db, data.get("container_loading_id"))
    container_no = str(data.get("container_no") or "").strip() or None
    invoice_date = _parse_date(data.get("invoice_date"))
    now = datetime.now(timezone.utc)
    row = LoadingInvoice(
        ref=ref,
        container_loading_id=loading_id,
        container_no=container_no,
        invoice_date=invoice_date,
        filename="manual",
        invoice_json=empty_invoice_json(ref=ref, container_no=container_no),
        created_at=now,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type=ENTITY,
        entity_id=row.id,
        before=None,
        after=snapshot(row, FIELDS),
        changed=[{"field": "ref", "old": None, "new": ref}],
        request=request,
    )
    db.commit()
    db.refresh(row)
    _attach_loading_marks(db, [row])
    return {"item": invoice_out(row)}


def update_header(db: Session, row: LoadingInvoice, data: dict[str, Any], user: User, request) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    if "ref" in data:
        row.ref = _normalize_ref(data.get("ref")) or row.ref
    if "container_loading_id" in data:
        row.container_loading_id = _resolve_loading_id(db, data.get("container_loading_id"))
    if "container_no" in data:
        row.container_no = str(data.get("container_no") or "").strip() or None
    if "invoice_date" in data:
        row.invoice_date = _parse_date(data.get("invoice_date"))
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = user.id
    db.flush()
    after = snapshot(row, FIELDS)
    write_audit(
        db,
        actor_user_id=user.id,
        action="update",
        entity_type=ENTITY,
        entity_id=row.id,
        before=before,
        after=after,
        changed=diff(before, after, FIELDS),
        request=request,
    )
    db.commit()
    db.refresh(row)
    _attach_loading_marks(db, [row])
    return {"item": invoice_out(row)}


def save_invoice(
    db: Session,
    row: LoadingInvoice,
    body: dict[str, Any],
    user: User,
    request,
) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    plan = normalize_invoice_payload({**body, "filename": row.filename or "manual"})
    row.ref = str(plan.get("ref") or row.ref)
    row.container_no = plan.get("container_no") or row.container_no
    if plan.get("invoice_date"):
        row.invoice_date = _parse_date(plan.get("invoice_date"))
    if "container_loading_id" in body:
        row.container_loading_id = _resolve_loading_id(db, body.get("container_loading_id"))
    if not row.filename:
        row.filename = "manual"
    row.invoice_json = plan
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = user.id
    db.flush()
    after = snapshot(row, FIELDS)
    write_audit(
        db,
        actor_user_id=user.id,
        action="update_invoice",
        entity_type=ENTITY,
        entity_id=row.id,
        before=before,
        after=after,
        changed=[
            {
                "field": "invoice",
                "old": None,
                "new": f"{row.filename} ({plan.get('line_count') or 0} lines)",
            }
        ],
        request=request,
    )
    db.commit()
    db.refresh(row)
    _attach_loading_marks(db, [row])
    return {"item": invoice_out(row)}


def set_invoice_file(
    db: Session,
    row: LoadingInvoice,
    plan: dict[str, Any],
    *,
    filename: str,
    user: User,
    request,
) -> dict[str, Any]:
    if row.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    before = snapshot(row, FIELDS)
    row.invoice_json = plan
    row.filename = filename
    if plan.get("ref"):
        row.ref = str(plan["ref"])
    if plan.get("container_no") and not row.container_no:
        row.container_no = str(plan["container_no"])
    if plan.get("invoice_date") and not row.invoice_date:
        row.invoice_date = _parse_date(plan.get("invoice_date"))
    # Auto-link by matching loading mark to invoice ref when unset
    if row.container_loading_id is None and row.ref:
        match = db.scalar(
            select(ContainerLoading).where(
                func.lower(ContainerLoading.mark) == row.ref.lower(),
                ContainerLoading.deleted_at.is_(None),
            )
        )
        if match is not None:
            row.container_loading_id = match.id
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = user.id
    db.flush()
    after = snapshot(row, FIELDS)
    write_audit(
        db,
        actor_user_id=user.id,
        action="upload_invoice",
        entity_type=ENTITY,
        entity_id=row.id,
        before=before,
        after=after,
        changed=[
            {
                "field": "invoice",
                "old": None,
                "new": f"{filename} ({plan.get('line_count') or 0} lines)",
            }
        ],
        request=request,
    )
    db.commit()
    db.refresh(row)
    _attach_loading_marks(db, [row])
    return {"item": invoice_out(row)}


def delete_row(db: Session, row: LoadingInvoice, user: User, request) -> dict[str, Any]:
    mark_deleted(db, row, user, request, ENTITY, FIELDS)
    db.refresh(row)
    return {"item": invoice_out(row, summary_only=True)}


def restore_row(db: Session, row: LoadingInvoice, user: User, request) -> dict[str, Any]:
    mark_restored(db, row, user, request, ENTITY, FIELDS)
    db.refresh(row)
    _attach_loading_marks(db, [row])
    return {"item": invoice_out(row)}


def invoices_for_loading(db: Session, loading_id: int) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(LoadingInvoice).where(
                LoadingInvoice.container_loading_id == loading_id,
                LoadingInvoice.deleted_at.is_(None),
            )
        ).all()
    )
    return [{"id": row.id, "ref": row.ref} for row in rows]
