"""Model-base agent: extract product fields from multi-side photos for one line."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import generate_content, model_name, provider
from app.agents.trace import Trace
from app.audit import write_audit
from app.cargo_files import IMAGE_INVOICE_LINE_ENTITY
from app.errors import AppError
from app.image_invoices import ENTITY, line_out
from app.models import CargoFile, ImageInvoice, ImageInvoiceLine, User
from app.present import num
from app.prompt_store import get_active_prompt

PROMPT_KEY = "invoice_image.product"
LINE_TEXT_FIELDS = ("brand_name", "barcode", "made_in", "volume")


def _object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object in response")
    data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _quantity(value: Any) -> Decimal | None:
    if value in (None, "", False):
        return None
    if isinstance(value, bool):
        return None
    try:
        qty = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    if qty < 0:
        return None
    return qty


def normalize_extract(data: dict[str, Any]) -> dict[str, Any]:
    qty = _quantity(data.get("quantity"))
    return {
        "brand_name": _text(data.get("brand_name")),
        "barcode": _text(data.get("barcode")),
        "made_in": _text(data.get("made_in")),
        "volume": _text(data.get("volume")),
        "quantity": float(qty) if qty is not None else None,
    }


def _line_files(db: Session, line_id: int) -> list[CargoFile]:
    return list(
        db.scalars(
            select(CargoFile)
            .where(
                CargoFile.entity_type == IMAGE_INVOICE_LINE_ENTITY,
                CargoFile.entity_id == str(line_id),
                CargoFile.deleted_at.is_(None),
                CargoFile.kind == "product",
            )
            .order_by(CargoFile.id.asc())
        ).all()
    )


def _llm_extract(
    *,
    user: User,
    line_id: int,
    files: list[tuple[bytes, str]],
) -> dict[str, Any]:
    prompt = get_active_prompt(PROMPT_KEY)
    parsed: dict[str, Any] | None = None
    with Trace(
        PROMPT_KEY,
        actor_user_id=user.id,
        entity_type="image_invoice_line",
        entity_id=str(line_id),
        input_json={"prompt": prompt, "file_count": len(files)},
    ) as run:
        text = ""
        for max_tokens in (1024, 4096):
            t0 = time.perf_counter()
            result = generate_content(
                prompt=prompt,
                files=files,
                max_tokens=max_tokens,
                thinking_budget=0,
            )
            llm_ms = max(0, int((time.perf_counter() - t0) * 1000))
            text = result["text"]
            finish = result["finish"]
            run.step(
                "llm",
                input={"max_tokens": max_tokens, "provider": provider(), "model": model_name()},
                output={
                    "finish": finish,
                    "text": text,
                    "usage": result.get("usage"),
                    "provider": result.get("provider") or provider(),
                    "model": result.get("model") or model_name(),
                },
                duration_ms=llm_ms,
            )
            if not text.strip():
                continue
            try:
                t1 = time.perf_counter()
                parsed = _object(text)
                parse_ms = max(0, int((time.perf_counter() - t1) * 1000))
            except (json.JSONDecodeError, ValueError) as exc:
                run.step("parse", input={"finish": finish}, error=str(exc), duration_ms=0)
                if finish.upper() not in {"MAX_TOKENS", "LENGTH"}:
                    break
                continue
            run.step("parse", output=parsed, duration_ms=parse_ms)
            run.pending_output = parsed
            break
        if parsed is None:
            run.pending_output = {"text": text}
            raise AppError(422, {"message": "Could not parse AI response. Try again."})
    return normalize_extract(parsed)


def _merge_fields(
    line: ImageInvoiceLine,
    extracted: dict[str, Any],
    *,
    overwrite: bool,
) -> list[str]:
    changed: list[str] = []
    for field in LINE_TEXT_FIELDS:
        new_val = extracted.get(field)
        if new_val in (None, ""):
            continue
        current = getattr(line, field)
        if current and not overwrite:
            continue
        if current != new_val:
            setattr(line, field, new_val)
            changed.append(field)
    qty = extracted.get("quantity")
    if qty is not None:
        if line.quantity is None or overwrite:
            try:
                new_qty = Decimal(str(qty))
            except (InvalidOperation, ValueError):
                new_qty = None
            if new_qty is not None and line.quantity != new_qty:
                line.quantity = new_qty
                changed.append("quantity")
    return changed


def extract_line(
    db: Session,
    invoice: ImageInvoice,
    line: ImageInvoiceLine,
    user: User,
    request,
    *,
    overwrite: bool = False,
    file_ids: list[int] | None = None,
) -> dict[str, Any]:
    if invoice.deleted_at is not None:
        raise AppError(400, {"message": "Cannot extract on a deleted invoice"})
    files = _line_files(db, line.id)
    if file_ids:
        wanted = set(file_ids)
        files = [row for row in files if row.id in wanted]
    if not files:
        raise AppError(422, {"message": "Upload product photos for this row first"})

    payloads: list[tuple[bytes, str]] = []
    for file_row in files:
        path = Path(file_row.stored_path)
        if not path.is_file():
            continue
        payloads.append((path.read_bytes(), file_row.mime or "image/jpeg"))
    if not payloads:
        raise AppError(422, {"message": "Stored photos are missing on disk"})

    extracted = _llm_extract(user=user, line_id=line.id, files=payloads)
    changed = _merge_fields(line, extracted, overwrite=overwrite)
    line.updated_at = datetime.now(timezone.utc)
    invoice.updated_at = line.updated_at
    invoice.updated_by = user.id
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="extract_line",
        entity_type=ENTITY,
        entity_id=invoice.id,
        before=None,
        after={"line_id": line.id, "extracted": extracted, "changed": changed},
        changed=[{"field": "lines", "old": None, "new": f"AI fill line #{line.id}: {', '.join(changed) or 'no changes'}"}],
        request=request,
    )
    db.commit()
    db.refresh(line)
    from app.cargo_files import counts_for

    counts = counts_for(db, IMAGE_INVOICE_LINE_ENTITY, [line.id])
    return {
        "item": line_out(line, file_count=counts.get(line.id, 0)),
        "extracted": {**extracted, "quantity": num(extracted.get("quantity"))},
        "changed_fields": changed,
    }
