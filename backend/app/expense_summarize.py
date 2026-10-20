"""Summarize expense receipt photos into one structured JSON via Settings prompt."""

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
from app.cargo_files import EXPENSE_ENTITY, counts_for
from app.errors import AppError
from app.expenses import ENTITY, _ensure_budget, _parse_currency, expense_out
from app.models import CargoFile, Expense, User
from app.present import freeze
from app.prompt_store import get_active_prompt


def _object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Summary JSON must be an object")
    return data


def _blank(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    return str(value).strip()


def _date(value) -> str | None:
    text = _blank(value)
    if not text:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", text)
    if match:
        year = match.group(3)
        if len(year) == 2:
            year = "20" + year
        return f"{year}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"
    return text


def _number(value) -> int | float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return freeze(value)
    match = re.search(r"(\d+(?:\.\d+)?)", _blank(value).replace(",", ""))
    if not match:
        return None
    number = float(match.group(1))
    return int(number) if number.is_integer() else number


def _text(value) -> str | None:
    text = re.sub(r"\s+", " ", _blank(value))
    return text or None


def normalize_summary(data: dict) -> dict[str, Any]:
    items = data.get("line_items")
    line_items = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            line_items.append(
                {
                    "description": _text(item.get("description")),
                    "qty": _number(item.get("qty")),
                    "amount": _number(item.get("amount")),
                }
            )
    currency = _text(data.get("currency"))
    if currency:
        currency = currency.upper()
        if currency in {"DHS", "DH", "DIRHAM", "د.إ"}:
            currency = "AED"
    return {
        "vendor": _text(data.get("vendor")),
        "date": _date(data.get("date")),
        "amount": _number(data.get("amount") if data.get("amount") is not None else data.get("total")),
        "currency": currency,
        "receipt_no": _text(data.get("receipt_no")),
        "category": _text(data.get("category")),
        "payment_method": _text(data.get("payment_method")),
        "vat_amount": _number(data.get("vat_amount")),
        "subtotal": _number(data.get("subtotal")),
        "total": _number(data.get("total")),
        "line_items": line_items,
        "notes": _text(data.get("notes")),
        "raw_text": _text(data.get("raw_text")),
    }


def _receipt_files(db: Session, expense_id: int) -> list[CargoFile]:
    return list(
        db.scalars(
            select(CargoFile)
            .where(
                CargoFile.entity_type == EXPENSE_ENTITY,
                CargoFile.entity_id == str(expense_id),
                CargoFile.deleted_at.is_(None),
                CargoFile.kind == "receipt",
            )
            .order_by(CargoFile.id.asc())
        ).all()
    )


def summarize_expense(db: Session, row: Expense, user: User, request) -> dict[str, Any]:
    files = _receipt_files(db, row.id)
    if not files:
        raise AppError(422, {"message": "Upload at least one receipt photo first"})
    attachments: list[tuple[bytes, str]] = []
    for file_row in files:
        path = Path(file_row.stored_path)
        if not path.is_file():
            continue
        attachments.append((path.read_bytes(), file_row.mime))
    if not attachments:
        raise AppError(422, {"message": "Stored receipt files are missing"})

    prompt = get_active_prompt("expenses.receipt")
    summary: dict[str, Any] | None = None
    with Trace(
        "expenses.receipt",
        actor_user_id=user.id,
        entity_type=ENTITY,
        entity_id=str(row.id),
        input_json={"prompt": prompt, "file_count": len(attachments)},
    ) as run:
        text = ""
        for max_tokens in (2048, 8192):
            t0 = time.perf_counter()
            result = generate_content(
                prompt=prompt,
                files=attachments,
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
                summary = normalize_summary(_object(text))
                parse_ms = max(0, int((time.perf_counter() - t1) * 1000))
            except (json.JSONDecodeError, ValueError) as exc:
                run.step("parse", input={"finish": finish}, error=str(exc), duration_ms=0)
                if finish.upper() not in {"MAX_TOKENS", "LENGTH"}:
                    break
                continue
            run.step("parse", output=summary, duration_ms=parse_ms)
            run.pending_output = summary
            break
        if summary is None:
            run.pending_output = {"text": text}
            raise AppError(422, {"message": "Could not summarize these receipts. Try again."})

    before = {
        "amount": freeze(row.amount),
        "currency": row.currency,
        "date": row.date.isoformat() if row.date else None,
        "summary": row.summary_json,
    }
    row.summary_json = summary
    filled: list[str] = []
    if row.amount is None and summary.get("amount") is not None:
        try:
            amount = Decimal(str(summary["amount"]))
        except (InvalidOperation, ValueError):
            amount = None
        if amount is not None and amount > 0:
            currency = row.currency or "AED"
            if summary.get("currency"):
                try:
                    currency = _parse_currency(summary["currency"])
                except AppError:
                    currency = row.currency or "AED"
            _ensure_budget(db, amount, currency, exclude_id=row.id)
            row.amount = amount
            row.currency = currency
            filled.extend(["amount", "currency"])
    if (not row.currency or row.currency == "AED") and summary.get("currency") and "currency" not in filled:
        # only fill currency when amount was empty path didn't set it and currency still default/empty
        if row.amount is None:
            try:
                row.currency = _parse_currency(summary["currency"])
                filled.append("currency")
            except AppError:
                pass
    if row.notes in (None, "") and summary.get("notes"):
        row.notes = summary["notes"]
        filled.append("notes")
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = user.id
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="summarize",
        entity_type=ENTITY,
        entity_id=str(row.id),
        before=before,
        after={"summary": summary, "filled": filled},
        changed=[
            {
                "field": "summary",
                "old": None,
                "new": summary.get("vendor") or str(summary.get("amount") or "receipt summary"),
            }
        ],
        request=request,
    )
    db.commit()
    db.refresh(row)
    return {
        "item": expense_out(row, file_count=counts_for(db, EXPENSE_ENTITY, [row.id]).get(row.id, 0)),
        "summary": summary,
    }
