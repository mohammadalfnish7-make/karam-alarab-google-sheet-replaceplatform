from sqlalchemy import String, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.constants import AIR_STATUSES, EXIT_STATUSES, SEA_STAGES
from app.models import AirCargo, ExitRecord, SeaCargo
from app.records import like_pattern


def _active_count(db: Session, model, *extra) -> int:
    stmt = select(func.count()).select_from(model).where(model.deleted_at.is_(None), *extra)
    return int(db.scalar(stmt) or 0)


def _carton_total(db: Session, model) -> int:
    stmt = select(func.coalesce(func.sum(model.cartons), 0)).where(model.deleted_at.is_(None))
    return int(db.scalar(stmt) or 0)


def _labeled_counts(db: Session, model, column, labels: list[str]) -> list[dict]:
    rows = db.execute(
        select(column, func.count()).where(model.deleted_at.is_(None)).group_by(column)
    ).all()
    found = {("" if label is None else str(label)): int(count) for label, count in rows}
    ordered = [{"label": label, "count": found.pop(label, 0)} for label in labels]
    for label, count in sorted(found.items(), key=lambda item: (-item[1], item[0])):
        ordered.append({"label": label or "Blank", "count": count})
    return ordered


def dashboard_summary(db: Session) -> dict:
    def section(model, column, labels: list[str]) -> dict:
        return {
            "rows": _active_count(db, model),
            "needs_review": _active_count(db, model, model.needs_review.is_(True)),
            "cartons": _carton_total(db, model),
            "breakdown": _labeled_counts(db, model, column, labels),
        }

    return {
        "sea": section(SeaCargo, SeaCargo.stage, SEA_STAGES),
        "air": section(AirCargo, AirCargo.status, AIR_STATUSES),
        "exit": section(ExitRecord, ExitRecord.status, EXIT_STATUSES),
    }


def _shipment_select():
    sea = select(
        SeaCargo.id.label("id"),
        cast(literal("sea"), String).label("kind"),
        SeaCargo.date_received.label("date_received"),
        SeaCargo.customer_code.label("customer_code"),
        SeaCargo.company_name.label("company_name"),
        SeaCargo.cartons.label("cartons"),
        SeaCargo.system_code.label("system_code"),
        SeaCargo.shipment_number.label("shipment_number"),
        SeaCargo.shipping_route.label("shipping_route"),
        SeaCargo.stage.label("progress"),
        SeaCargo.needs_review.label("needs_review"),
    ).where(SeaCargo.deleted_at.is_(None))
    air = select(
        AirCargo.id.label("id"),
        cast(literal("air"), String).label("kind"),
        AirCargo.date_received.label("date_received"),
        AirCargo.customer_code.label("customer_code"),
        AirCargo.company_name.label("company_name"),
        AirCargo.cartons.label("cartons"),
        AirCargo.system_code.label("system_code"),
        AirCargo.shipment_number.label("shipment_number"),
        cast(literal(None), String).label("shipping_route"),
        AirCargo.status.label("progress"),
        AirCargo.needs_review.label("needs_review"),
    ).where(AirCargo.deleted_at.is_(None))
    return union_all(sea, air).subquery("shipments")


def list_shipments(
    db: Session,
    *,
    q: str | None,
    kind: str | None,
    progress: str | None,
    needs_review: bool | None,
    limit: int,
    offset: int,
) -> dict:
    rows = _shipment_select()
    filters = []
    if kind in {"sea", "air"}:
        filters.append(rows.c.kind == kind)
    if progress:
        filters.append(rows.c.progress == progress)
    if needs_review is not None:
        filters.append(rows.c.needs_review.is_(needs_review))
    if q and q.strip():
        pattern = like_pattern(q.strip())
        filters.append(
            or_(
                rows.c.customer_code.ilike(pattern, escape="\\"),
                rows.c.company_name.ilike(pattern, escape="\\"),
                rows.c.system_code.ilike(pattern, escape="\\"),
                rows.c.shipment_number.ilike(pattern, escape="\\"),
                rows.c.shipping_route.ilike(pattern, escape="\\"),
                rows.c.progress.ilike(pattern, escape="\\"),
            )
        )
    count_stmt = select(func.count()).select_from(rows)
    stmt = select(rows)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    total = int(db.scalar(count_stmt) or 0)
    stmt = stmt.order_by(rows.c.date_received.is_(None), rows.c.date_received.desc(), rows.c.id.desc())
    found = db.execute(stmt.offset(offset).limit(limit)).all()
    items = []
    for row in found:
        received = row.date_received
        items.append(
            {
                "kind": row.kind,
                "id": row.id,
                "date_received": received.isoformat() if received else None,
                "customer_code": row.customer_code,
                "company_name": row.company_name,
                "cartons": row.cartons,
                "system_code": row.system_code,
                "shipment_number": row.shipment_number,
                "shipping_route": row.shipping_route,
                "progress": row.progress,
                "needs_review": bool(row.needs_review),
            }
        )
    return {"items": items, "total": total}
