"""Bird's-eye knowledge graph: actors, data types, processes, and live fill stats."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AirCargo,
    AirShipmentPicture,
    AirShipmentTrackerRow,
    AuditLog,
    ContainerLoading,
    ContainerRow,
    CooRow,
    DocumentExpiry,
    ExitRecord,
    Expense,
    FlightScheduleRow,
    LoadingInvoice,
    SeaCargo,
    User,
)
from app.present import iso

# Conceptual actors (roles in the work, not only DB users)
ACTORS = [
    {
        "id": "operator",
        "label": "Operator",
        "kind": "role",
        "summary": "Day-to-day entry: cargo, exits, trackers, loading, invoices, expenses, photos.",
    },
    {
        "id": "admin",
        "label": "Admin",
        "kind": "role",
        "summary": "Users, settings, restores, oversight dashboards, agent runs.",
    },
    {
        "id": "excel_import",
        "label": "Excel import",
        "kind": "system",
        "summary": "Startup bulk load from load-plan and container-tracker workbooks.",
    },
    {
        "id": "llm",
        "label": "LLM agents",
        "kind": "system",
        "summary": "Reads delivery notes, scales, PDFs, loading photos, receipts into structured fields.",
    },
    {
        "id": "customer",
        "label": "Customer (external)",
        "kind": "external",
        "summary": "Appears as TL marks / customer codes on cargo and plans — not an app login.",
    },
    {
        "id": "supplier",
        "label": "Supplier / company (external)",
        "kind": "external",
        "summary": "Company names on cargo, exit suppliers, invoice shops — reference data.",
    },
]

DATA_TYPES = [
    {
        "id": "sea_cargo",
        "label": "Sea cargo",
        "route": "/sea",
        "fields": ["date_received", "customer_code", "company_name", "cartons", "weights", "system_code", "shipment_number", "route", "stage"],
        "evidence": ["note photos", "scale photos"],
    },
    {
        "id": "air_cargo",
        "label": "Air cargo",
        "route": "/air",
        "fields": ["date_received", "customer_code", "company_name", "cartons", "weights", "shipment_number", "status"],
        "evidence": ["note photos", "scale photos"],
    },
    {
        "id": "exit_record",
        "label": "Exit / customs",
        "route": "/exit",
        "fields": ["no", "mark", "supplier", "invoice_no", "cartons", "date_of_submission", "status"],
        "evidence": [],
    },
    {
        "id": "container_row",
        "label": "Container tracker",
        "route": "/containers",
        "fields": ["container_no", "inv_no", "kgs", "carton", "driver", "stage", "status", "supplier_buyer"],
        "evidence": ["optional files"],
    },
    {
        "id": "air_shipment_tracker",
        "label": "Air tracker",
        "route": "/air-tracker",
        "fields": ["ref", "vendor", "airline", "AWB", "cartons", "weight", "status"],
        "evidence": [],
    },
    {
        "id": "coo_row",
        "label": "COO",
        "route": "/coo",
        "fields": ["SR", "inv_number", "container_no", "kjs", "grg", "k_exit"],
        "evidence": [],
    },
    {
        "id": "flight_schedule",
        "label": "Flight schedule",
        "route": "/flight-schedule",
        "fields": ["airline", "date", "narrow/wide", "status"],
        "evidence": [],
    },
    {
        "id": "container_loading",
        "label": "Container loading",
        "route": "/container-loading",
        "fields": ["mark", "container_no", "plan lines (mix/name/ctn/kg)", "photo marks", "plan check"],
        "evidence": ["loading photos", "plan Excel"],
    },
    {
        "id": "loading_invoice",
        "label": "Loading invoice",
        "route": "/invoices",
        "fields": ["ref", "container", "date", "mark/shop/description/COO/pcs/HS/type/ctn/weight"],
        "evidence": ["invoice Excel"],
    },
    {
        "id": "expense",
        "label": "Expenses (Qusai)",
        "route": "/expenses",
        "fields": ["mark", "date", "amount", "currency", "notes", "receipt summary"],
        "evidence": ["receipt photos"],
    },
    {
        "id": "air_shipment_picture",
        "label": "Air shipment pictures",
        "route": "/air-shipment-pictures",
        "fields": ["number", "date", "cartons"],
        "evidence": ["shipment photos"],
    },
    {
        "id": "document_expiry",
        "label": "Document expiry",
        "route": "/expiry",
        "fields": ["company/employee/vehicle", "doc type", "expiry_date"],
        "evidence": [],
    },
    {
        "id": "lookups",
        "label": "Lookups",
        "route": None,
        "fields": ["customers (TL)", "companies", "suppliers"],
        "evidence": [],
    },
    {
        "id": "pdf_document",
        "label": "PDF extract",
        "route": "/pdf",
        "fields": ["uploaded PDF → confirmed sea/air/exit rows"],
        "evidence": ["PDF files"],
    },
]

PROCESSES = [
    {
        "id": "receive_cargo",
        "label": "1. Receive cargo",
        "summary": "Operator creates sea/air rows; optional intake LLM from note/scale photos or PDF confirm.",
        "steps": ["Create sea/air row", "Attach note/scale", "LLM read (optional)", "Set stage/status"],
    },
    {
        "id": "move_warehouse",
        "label": "2. Move through warehouse / air",
        "summary": "Stage (sea) or status (air) updates as goods progress toward loading or delivery.",
        "steps": ["Update stage/status", "Tracker overview"],
    },
    {
        "id": "track_container",
        "label": "3. Track containers & related sheets",
        "summary": "Container tracker stages, air tracker, COO, flight schedule — shared logistics picture.",
        "steps": ["Update container stage", "Link invoices/QR", "Maintain COO / flights"],
    },
    {
        "id": "load_container",
        "label": "4. Load container",
        "summary": "Loading mark → photos → extract → plan → check → link packing invoice.",
        "steps": ["Create loading mark", "Upload photos + extract", "Edit/upload plan", "Check vs photos", "Link invoice"],
    },
    {
        "id": "exit_customs",
        "label": "5. Exit / customs",
        "summary": "Exit records with supplier and invoice numbers for submission tracking.",
        "steps": ["Create exit row", "Set invoice numbers", "Update status"],
    },
    {
        "id": "spend_track",
        "label": "6. Expenses & compliance",
        "summary": "Qusai expenses with receipts; document expiry reminders.",
        "steps": ["Log expense + receipts", "Summarize (LLM)", "Watch expiry dates"],
    },
]

# actor → data they typically fill/own
ACTOR_FILLS = [
    ("operator", "sea_cargo", "creates & updates"),
    ("operator", "air_cargo", "creates & updates"),
    ("operator", "exit_record", "creates & updates"),
    ("operator", "container_row", "creates & updates"),
    ("operator", "air_shipment_tracker", "creates & updates"),
    ("operator", "coo_row", "creates & updates"),
    ("operator", "flight_schedule", "creates & updates"),
    ("operator", "container_loading", "creates, photos, plan, check"),
    ("operator", "loading_invoice", "creates, lines, Excel"),
    ("operator", "expense", "creates, receipts"),
    ("operator", "air_shipment_picture", "creates, photos"),
    ("operator", "document_expiry", "updates"),
    ("operator", "lookups", "adds missing codes/names when saving"),
    ("operator", "pdf_document", "uploads & confirms"),
    ("admin", "lookups", "manages users/settings (related)"),
    ("admin", "sea_cargo", "restore / review oversight"),
    ("admin", "air_cargo", "restore / review oversight"),
    ("admin", "exit_record", "restore / review oversight"),
    ("admin", "container_loading", "restore"),
    ("admin", "loading_invoice", "restore"),
    ("admin", "expense", "restore / budget view"),
    ("excel_import", "sea_cargo", "bulk import"),
    ("excel_import", "air_cargo", "bulk import"),
    ("excel_import", "exit_record", "bulk import"),
    ("excel_import", "container_row", "bulk import"),
    ("excel_import", "air_shipment_tracker", "bulk import"),
    ("excel_import", "coo_row", "bulk import"),
    ("excel_import", "document_expiry", "bulk import"),
    ("llm", "sea_cargo", "intake note/scale + PDF extract"),
    ("llm", "air_cargo", "intake note/scale + PDF extract"),
    ("llm", "exit_record", "PDF extract"),
    ("llm", "container_loading", "photo extract + plan check assist"),
    ("llm", "expense", "receipt summarize"),
    ("customer", "sea_cargo", "identity via customer_code / mark"),
    ("customer", "air_cargo", "identity via customer_code"),
    ("customer", "container_loading", "marks on plan/photos"),
    ("customer", "loading_invoice", "MARK column"),
    ("supplier", "sea_cargo", "company_name"),
    ("supplier", "exit_record", "supplier"),
    ("supplier", "loading_invoice", "SHOP column"),
    ("supplier", "container_row", "supplier_buyer"),
]

# process → data types involved
PROCESS_USES = [
    ("receive_cargo", "sea_cargo"),
    ("receive_cargo", "air_cargo"),
    ("receive_cargo", "pdf_document"),
    ("receive_cargo", "lookups"),
    ("move_warehouse", "sea_cargo"),
    ("move_warehouse", "air_cargo"),
    ("track_container", "container_row"),
    ("track_container", "air_shipment_tracker"),
    ("track_container", "coo_row"),
    ("track_container", "flight_schedule"),
    ("track_container", "air_shipment_picture"),
    ("load_container", "container_loading"),
    ("load_container", "loading_invoice"),
    ("load_container", "container_row"),
    ("exit_customs", "exit_record"),
    ("exit_customs", "lookups"),
    ("spend_track", "expense"),
    ("spend_track", "document_expiry"),
]

# shared keys / handoffs between data types
SHARES = [
    {"from": "sea_cargo", "to": "exit_record", "via": "customer mark / shipment context", "note": "Same marks often appear across cargo and exit."},
    {"from": "air_cargo", "to": "air_shipment_picture", "via": "AR shipment number", "note": "Pictures module uses AR-style numbers."},
    {"from": "air_cargo", "to": "air_shipment_tracker", "via": "ref / AWB / cartons", "note": "Air ops tracked in two sheets historically."},
    {"from": "container_row", "to": "container_loading", "via": "container_no / mark", "note": "Loading can link to a tracker container."},
    {"from": "container_loading", "to": "loading_invoice", "via": "container_loading_id / ref≈mark", "note": "Invoice packing list linked to a loading job."},
    {"from": "container_row", "to": "coo_row", "via": "container_no / inv", "note": "COO sheet references containers."},
    {"from": "exit_record", "to": "coo_row", "via": "k_exit / invoices", "note": "Customs and COO share invoice/container context."},
    {"from": "lookups", "to": "sea_cargo", "via": "customer_code / company_name", "note": "Lookups constrain and grow from cargo saves."},
    {"from": "lookups", "to": "exit_record", "via": "mark / supplier", "note": "Exit uses customer marks and suppliers."},
    {"from": "pdf_document", "to": "sea_cargo", "via": "confirm extract", "note": "PDF confirm creates cargo/exit rows."},
    {"from": "pdf_document", "to": "air_cargo", "via": "confirm extract", "note": "PDF confirm creates air rows."},
    {"from": "pdf_document", "to": "exit_record", "via": "confirm extract", "note": "PDF confirm creates exit rows."},
]

ENTITY_LABELS = {item["id"]: item["label"] for item in DATA_TYPES}

# Map audit entity_type strings → knowledge data ids
AUDIT_ENTITY_MAP = {
    "sea_cargo": "sea_cargo",
    "air_cargo": "air_cargo",
    "exit_record": "exit_record",
    "container_row": "container_row",
    "air_shipment_tracker_row": "air_shipment_tracker",
    "air_tracker": "air_shipment_tracker",
    "coo_row": "coo_row",
    "flight_schedule_row": "flight_schedule",
    "container_loading": "container_loading",
    "loading_invoice": "loading_invoice",
    "expense": "expense",
    "air_shipment_picture": "air_shipment_picture",
    "document_expiry": "document_expiry",
    "pdf_document": "pdf_document",
    "customer": "lookups",
    "company": "lookups",
    "supplier": "lookups",
}


def _record_counts(db: Session) -> dict[str, int]:
    pairs: list[tuple[str, Any]] = [
        ("sea_cargo", SeaCargo),
        ("air_cargo", AirCargo),
        ("exit_record", ExitRecord),
        ("container_row", ContainerRow),
        ("air_shipment_tracker", AirShipmentTrackerRow),
        ("coo_row", CooRow),
        ("flight_schedule", FlightScheduleRow),
        ("container_loading", ContainerLoading),
        ("loading_invoice", LoadingInvoice),
        ("expense", Expense),
        ("air_shipment_picture", AirShipmentPicture),
        ("document_expiry", DocumentExpiry),
    ]
    out: dict[str, int] = {}
    for key, model in pairs:
        deleted = getattr(model, "deleted_at", None)
        stmt = select(func.count()).select_from(model)
        if deleted is not None:
            stmt = stmt.where(deleted.is_(None))
        out[key] = int(db.scalar(stmt) or 0)
    return out


def _live_fills(db: Session) -> dict[str, Any]:
    rows = db.execute(
        select(
            AuditLog.actor_user_id,
            AuditLog.entity_type,
            AuditLog.action,
            func.count().label("n"),
            func.max(AuditLog.created_at).label("last_at"),
        )
        .where(AuditLog.entity_type.is_not(None))
        .group_by(AuditLog.actor_user_id, AuditLog.entity_type, AuditLog.action)
    ).all()

    user_ids = {row.actor_user_id for row in rows if row.actor_user_id is not None}
    users = {
        user.id: user
        for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    } if user_ids else {}

    by_actor: dict[str, dict[str, Any]] = {}
    by_entity: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"creates": 0, "updates": 0, "deletes": 0, "other": 0, "actors": set()}
    )

    for row in rows:
        data_id = AUDIT_ENTITY_MAP.get(row.entity_type or "", row.entity_type or "other")
        action = (row.action or "").lower()
        count = int(row.n or 0)
        ent = by_entity[data_id]
        if action in ("create", "upload", "upload_invoice", "confirm"):
            ent["creates"] += count
        elif action in ("update", "update_invoice", "update_plan", "photos", "summarize"):
            ent["updates"] += count
        elif action in ("delete", "soft_delete"):
            ent["deletes"] += count
        else:
            ent["other"] += count

        if row.actor_user_id is None:
            actor_key = "system"
            email = "system / import"
            role = "system"
        else:
            user = users.get(row.actor_user_id)
            actor_key = f"user:{row.actor_user_id}"
            email = user.email if user else f"user#{row.actor_user_id}"
            role = user.role if user else "unknown"
            ent["actors"].add(actor_key)

        bucket = by_actor.setdefault(
            actor_key,
            {
                "id": actor_key,
                "user_id": row.actor_user_id,
                "email": email,
                "role": role,
                "fills": {},
                "last_at": None,
            },
        )
        fill = bucket["fills"].setdefault(
            data_id,
            {"data_id": data_id, "label": ENTITY_LABELS.get(data_id, data_id), "actions": {}, "total": 0},
        )
        fill["actions"][action] = fill["actions"].get(action, 0) + count
        fill["total"] += count
        last = iso(row.last_at)
        if last and (bucket["last_at"] is None or last > bucket["last_at"]):
            bucket["last_at"] = last

    actor_list = []
    for bucket in by_actor.values():
        fills = sorted(bucket["fills"].values(), key=lambda item: item["total"], reverse=True)
        actor_list.append({**bucket, "fills": fills})
    actor_list.sort(key=lambda item: (-sum(f["total"] for f in item["fills"]), item["email"]))

    entity_list = []
    for data_id, ent in by_entity.items():
        entity_list.append(
            {
                "data_id": data_id,
                "label": ENTITY_LABELS.get(data_id, data_id),
                "creates": ent["creates"],
                "updates": ent["updates"],
                "deletes": ent["deletes"],
                "other": ent["other"],
                "unique_actors": len(ent["actors"]),
            }
        )
    entity_list.sort(key=lambda item: (-(item["creates"] + item["updates"]), item["label"]))

    return {"by_actor": actor_list, "by_entity": entity_list}


def knowledge_graph(db: Session) -> dict[str, Any]:
    counts = _record_counts(db)
    live = _live_fills(db)
    data_types = [
        {**item, "record_count": counts.get(item["id"])} for item in DATA_TYPES
    ]
    return {
        "actors": ACTORS,
        "data_types": data_types,
        "processes": PROCESSES,
        "fills": [
            {"actor_id": a, "data_id": d, "relation": rel} for a, d, rel in ACTOR_FILLS
        ],
        "process_uses": [
            {"process_id": p, "data_id": d} for p, d in PROCESS_USES
        ],
        "shares": SHARES,
        "live": live,
        "record_counts": counts,
    }
