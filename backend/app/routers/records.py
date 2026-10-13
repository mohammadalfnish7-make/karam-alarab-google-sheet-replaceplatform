from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.audit import history_for
from app.constants import ENTITY_TYPES
from app.deps import get_current_user, get_db, require_admin
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
        return cargo_out(visible(db.get(model, item_id), user), kind)

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
