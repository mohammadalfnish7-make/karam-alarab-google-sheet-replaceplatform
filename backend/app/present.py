from datetime import date, datetime
from decimal import Decimal
from typing import Any


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def freeze(value: Any) -> Any:
    if isinstance(value, Decimal):
        number = float(value)
        if number.is_integer():
            return int(number)
        return number
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: freeze(item) for key, item in value.items()}
    if isinstance(value, list):
        return [freeze(item) for item in value]
    return value


def num(value: Any) -> int | float | None:
    if value is None:
        return None
    return freeze(value)


SEA_FIELDS = [
    "date_received",
    "customer_code",
    "company_name",
    "cartons",
    "gross_weight_kg",
    "gross_is_no_pallet",
    "net_weight_kg",
    "system_code",
    "shipment_number",
    "shipping_route",
    "stage",
]

AIR_FIELDS = [
    "date_received",
    "customer_code",
    "company_name",
    "cartons",
    "gross_weight_kg",
    "gross_is_no_pallet",
    "net_weight_kg",
    "system_code",
    "shipment_number",
    "status",
]

EXIT_FIELDS = [
    "no",
    "mark",
    "supplier",
    "invoice_no",
    "cartons",
    "date_of_submission",
    "status",
]


def snapshot(row: Any, fields: list[str]) -> dict[str, Any]:
    data = {name: getattr(row, name) for name in fields}
    data["deleted_at"] = row.deleted_at
    data["deleted_by"] = row.deleted_by
    return freeze(data)


def diff(before: dict[str, Any], after: dict[str, Any], fields: list[str]) -> list[dict[str, Any]]:
    names = list(fields) + ["deleted_at", "deleted_by"]
    changes = []
    for name in names:
        if before.get(name) != after.get(name):
            changes.append({"field": name, "old": before.get(name), "new": after.get(name)})
    return changes


def meta(row: Any) -> dict[str, Any]:
    return {
        "created_at": iso(row.created_at),
        "created_by": row.created_by,
        "updated_at": iso(row.updated_at),
        "updated_by": row.updated_by,
        "deleted_at": iso(row.deleted_at),
        "deleted_by": row.deleted_by,
    }


def cargo_out(row: Any, kind: str) -> dict[str, Any]:
    data = {
        "id": row.id,
        "legacy": row.legacy,
        "needs_review": row.needs_review,
        "issues": row.issues or [],
        "date_received": iso(row.date_received),
        "customer_code": row.customer_code,
        "company_name": row.company_name,
        "cartons": row.cartons,
        "gross_weight_kg": num(row.gross_weight_kg),
        "gross_is_no_pallet": bool(row.gross_is_no_pallet),
        "net_weight_kg": num(row.net_weight_kg),
        "system_code": row.system_code,
        "shipment_number": row.shipment_number,
        **meta(row),
    }
    if kind == "sea":
        data["shipping_route"] = row.shipping_route
        data["stage"] = row.stage
    else:
        data["status"] = row.status
    return data


def exit_out(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "legacy": row.legacy,
        "needs_review": row.needs_review,
        "issues": row.issues or [],
        "no": row.no,
        "mark": row.mark,
        "supplier": row.supplier,
        "invoice_no": row.invoice_no,
        "cartons": row.cartons,
        "date_of_submission": iso(row.date_of_submission),
        "status": row.status,
        **meta(row),
    }


def audit_out(row: Any, email: str | None) -> dict[str, Any]:
    return {
        "id": row.id,
        "actor_user_id": row.actor_user_id,
        "actor_email": email,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "before_json": row.before_json,
        "after_json": row.after_json,
        "changed_fields": row.changed_fields or [],
        "ip": row.ip,
        "user_agent": row.user_agent,
        "created_at": iso(row.created_at),
    }


def user_out(user: Any) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": iso(user.created_at),
    }
