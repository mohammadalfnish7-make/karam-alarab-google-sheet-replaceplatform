"""CRUD for container-tracker workbook sheets."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.errors import AppError
from app.models import AirShipmentTrackerRow, ContainerRow, CooRow, FlightScheduleRow, User
from app.present import diff, freeze, iso, meta, num, snapshot
from app.records import like_pattern, mark_deleted, mark_restored, require_row, visible
from app.validation import parse_compact_dmy, parse_dmy

SHEETS: dict[str, dict[str, Any]] = {
    "containers": {
        "model": ContainerRow,
        "entity_type": "container_row",
        "fields": [
            "date",
            "inv_no",
            "qr",
            "previous_cont",
            "container_no",
            "kgs",
            "carton",
            "driver_name",
            "driver_contact",
            "info",
            "notes",
            "foreign_invoice",
            "russian_instrct",
            "supplier_buyer",
            "status",
            "stage",
            "extra_json",
        ],
        "search": [
            "inv_no",
            "qr",
            "previous_cont",
            "container_no",
            "driver_name",
            "driver_contact",
            "info",
            "notes",
            "foreign_invoice",
            "russian_instrct",
            "supplier_buyer",
            "status",
            "stage",
        ],
        "date_fields": {"date"},
        "int_fields": {"carton"},
        "number_fields": {"kgs"},
        "order": (ContainerRow.id.desc(),),
    },
    "air-tracker": {
        "model": AirShipmentTrackerRow,
        "entity_type": "air_shipment_tracker_row",
        "fields": [
            "ref_no",
            "vendor",
            "airline",
            "date",
            "item",
            "cartons",
            "weight_kg",
            "awb",
            "status",
            "comment",
            "extra_json",
        ],
        "search": ["ref_no", "vendor", "airline", "item", "awb", "status", "comment"],
        "date_fields": {"date"},
        "int_fields": {"cartons"},
        "number_fields": {"weight_kg"},
        "order": (AirShipmentTrackerRow.id.desc(),),
    },
    "coo": {
        "model": CooRow,
        "entity_type": "coo_row",
        "fields": ["sr", "inv_number", "container_no", "kjs", "grg", "k_exit", "extra_json"],
        "search": ["inv_number", "container_no", "kjs", "grg", "k_exit"],
        "date_fields": set(),
        "int_fields": {"sr"},
        "number_fields": set(),
        "order": (CooRow.id.desc(),),
    },
    "flight-schedule": {
        "model": FlightScheduleRow,
        "entity_type": "flight_schedule_row",
        "fields": ["sr", "airline", "date", "day", "narrow", "wide", "status", "column_1", "extra_json"],
        "search": ["airline", "day", "narrow", "wide", "status", "column_1"],
        "date_fields": {"date"},
        "int_fields": {"sr"},
        "number_fields": set(),
        "order": (FlightScheduleRow.id.desc(),),
    },
}


def sheet_out(kind: str, row) -> dict[str, Any]:
    cfg = SHEETS[kind]
    data = {
        "id": row.id,
        "legacy": row.legacy,
        "needs_review": row.needs_review,
        "issues": row.issues or [],
        **meta(row),
    }
    for name in cfg["fields"]:
        value = getattr(row, name)
        if name in cfg["date_fields"]:
            data[name] = iso(value)
        elif name in cfg["number_fields"]:
            data[name] = num(value)
        else:
            data[name] = freeze(value)
    return data


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return parse_dmy(text) or parse_compact_dmy(text)


def _parse_int(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    raise ValueError("not an integer")


def _parse_number(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("not a number")
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    number = float(text)
    return int(number) if number.is_integer() else number


def normalize_payload(kind: str, data: dict) -> tuple[dict, dict]:
    cfg = SHEETS[kind]
    values = {}
    errors = {}
    for name in cfg["fields"]:
        if name not in data:
            continue
        raw = data[name]
        try:
            if name in cfg["date_fields"]:
                values[name] = _parse_date(raw)
                if raw not in (None, "") and values[name] is None:
                    errors[name] = "Enter a valid date"
            elif name in cfg["int_fields"]:
                values[name] = _parse_int(raw)
            elif name in cfg["number_fields"]:
                values[name] = _parse_number(raw)
            elif name == "extra_json":
                values[name] = raw if isinstance(raw, (dict, list)) or raw is None else None
            else:
                if raw is None:
                    values[name] = None
                else:
                    text = str(raw).strip()
                    values[name] = text or None
        except (TypeError, ValueError):
            errors[name] = "Invalid value"
    return values, errors


def list_sheet(
    db: Session,
    kind: str,
    *,
    q: str | None,
    needs_review: bool | None,
    include_deleted: bool,
    limit: int,
    offset: int,
    user: User,
) -> dict:
    cfg = SHEETS[kind]
    model = cfg["model"]
    filters = []
    if not (include_deleted and user.role == "admin"):
        filters.append(model.deleted_at.is_(None))
    if needs_review is not None:
        filters.append(model.needs_review.is_(needs_review))
    if q and q.strip():
        pattern = like_pattern(q.strip())
        clauses = [getattr(model, name).ilike(pattern, escape="\\") for name in cfg["search"]]
        filters.append(or_(*clauses))
    count_stmt = select(func.count()).select_from(model)
    stmt = select(model)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(*cfg["order"]).offset(offset).limit(limit)).all()
    return {"items": [sheet_out(kind, row) for row in rows], "total": total}


def save_sheet(db: Session, kind: str, data: dict, user: User, request, existing=None) -> dict:
    cfg = SHEETS[kind]
    model = cfg["model"]
    values, errors = normalize_payload(kind, data)
    if errors:
        raise AppError(422, {"field_errors": errors, "warnings": []})
    now = datetime.now(timezone.utc)
    if existing is None:
        row = model(
            legacy=False,
            needs_review=False,
            issues=[],
            created_at=now,
            created_by=user.id,
        )
        for name in cfg["fields"]:
            setattr(row, name, values.get(name))
        before = {name: None for name in cfg["fields"]}
        before["deleted_at"] = None
        before["deleted_by"] = None
        action = "create"
        db.add(row)
    else:
        row = existing
        before = snapshot(row, cfg["fields"])
        action = "update"
        for name, value in values.items():
            setattr(row, name, value)
        row.updated_at = now
        row.updated_by = user.id
        if row.needs_review and row.issues:
            # clear review when user saves cleanly
            row.needs_review = False
            row.issues = []
    db.flush()
    after = snapshot(row, cfg["fields"])
    changed = diff(before, after, cfg["fields"])
    if action == "create" or changed:
        write_audit(
            db,
            actor_user_id=user.id,
            action=action,
            entity_type=cfg["entity_type"],
            entity_id=row.id,
            before=None if action == "create" else before,
            after=after,
            changed=changed,
            request=request,
        )
    db.commit()
    return {"item": sheet_out(kind, row), "warnings": []}


def get_row(db: Session, kind: str, item_id: int, user: User):
    cfg = SHEETS[kind]
    return visible(db.get(cfg["model"], item_id), user)


def delete_row(db: Session, kind: str, item_id: int, user: User, request):
    cfg = SHEETS[kind]
    row = visible(db.get(cfg["model"], item_id), user)
    mark_deleted(db, row, user, request, cfg["entity_type"], cfg["fields"])
    return {"ok": True}


def restore_row(db: Session, kind: str, item_id: int, user: User, request):
    cfg = SHEETS[kind]
    row = require_row(db.get(cfg["model"], item_id))
    mark_restored(db, row, user, request, cfg["entity_type"], cfg["fields"])
    return {"item": sheet_out(kind, row)}
