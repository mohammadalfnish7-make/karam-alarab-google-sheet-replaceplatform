"""Store and serve intake evidence files linked to cargo rows."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models import AirCargo, CargoFile, SeaCargo, User

_MAX_FILE = 15 * 1024 * 1024
_ALLOWED_MIME = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def require_cargo(db: Session, kind: str, item_id: int, user: User):
    model = SeaCargo if kind == "sea" else AirCargo
    row = db.get(model, item_id)
    if row is None or (row.deleted_at is not None and user.role != "admin"):
        raise AppError(404, {"message": "Not found"})
    return row


def detect_mime(content: bytes, filename: str, declared: str | None) -> str:
    name = (filename or "").lower()
    declared = (declared or "").split(";")[0].strip().lower()
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG"):
        return "image/png"
    if declared in _ALLOWED_MIME:
        return "image/jpeg" if declared == "image/jpg" else declared
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    if name.endswith(".gif"):
        return "image/gif"
    raise AppError(422, {"message": f"Unsupported file type: {filename or 'upload'}"})


def file_out(row: CargoFile) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "label": row.label,
        "file_name": row.original_filename,
        "mime": row.mime,
        "sha256": row.sha256,
        "byte_size": row.byte_size,
        "extracted": row.extracted_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "is_image": row.mime.startswith("image/"),
        "is_pdf": row.mime == "application/pdf",
    }


def counts_for(db: Session, entity_type: str, entity_ids: list[int]) -> dict[int, int]:
    if not entity_ids:
        return {}
    keys = [str(item_id) for item_id in entity_ids]
    rows = db.execute(
        select(CargoFile.entity_id, func.count())
        .where(CargoFile.entity_type == entity_type, CargoFile.entity_id.in_(keys))
        .group_by(CargoFile.entity_id)
    ).all()
    return {int(entity_id): int(count) for entity_id, count in rows}


def list_files(db: Session, entity_type: str, entity_id: int) -> list[dict]:
    rows = db.scalars(
        select(CargoFile)
        .where(CargoFile.entity_type == entity_type, CargoFile.entity_id == str(entity_id))
        .order_by(CargoFile.id.asc())
    ).all()
    return [file_out(row) for row in rows]


def get_file(db: Session, entity_type: str, entity_id: int, file_id: int) -> CargoFile:
    row = db.get(CargoFile, file_id)
    if (
        row is None
        or row.entity_type != entity_type
        or row.entity_id != str(entity_id)
    ):
        raise AppError(404, {"message": "File not found"})
    path = Path(row.stored_path)
    if not path.is_file():
        raise AppError(404, {"message": "Stored file is missing"})
    return row


def store_file(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    kind: str,
    label: str,
    filename: str,
    content: bytes,
    mime: str,
    extracted: Any | None,
    user: User,
) -> CargoFile:
    if kind not in {"note", "scale"}:
        raise AppError(422, {"message": "File kind must be note or scale"})
    if not content:
        raise AppError(422, {"message": f"{filename or 'file'} is empty"})
    if len(content) > _MAX_FILE:
        raise AppError(422, {"message": f"{filename or 'file'} must be 15 MB or smaller"})
    mime = detect_mime(content, filename, mime)
    ext = _ALLOWED_MIME[mime]
    folder = Path(settings.upload_dir) / "cargo" / entity_type / str(entity_id)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}.{ext}"
    stored.write_bytes(content)
    row = CargoFile(
        entity_type=entity_type,
        entity_id=str(entity_id),
        kind=kind,
        label=(label or kind).strip()[:80] or kind,
        original_filename=(filename or f"file.{ext}")[:500],
        stored_path=str(stored.resolve()),
        mime=mime,
        sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        extracted_json=extracted,
        uploaded_by=user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def parse_extracted(raw: str | None) -> Any | None:
    if raw is None or raw == "":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"text": raw}
