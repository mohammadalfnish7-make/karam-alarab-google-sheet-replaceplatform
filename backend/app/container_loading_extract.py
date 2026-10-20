"""Per-image pallet/mark extract + plan check for standalone container loading."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import generate_content, model_name, provider
from app.agents.trace import Trace
from app.audit import write_audit
from app.cargo_files import LOADING_ENTITY, counts_for, file_out, get_file
from app.container_loading import ENTITY, loading_out
from app.errors import AppError
from app.models import CargoFile, ContainerLoading, User
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
        raise ValueError("JSON must be an object")
    return data


def _blank(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    return str(value).strip()


def _text(value) -> str | None:
    text = re.sub(r"\s+", " ", _blank(value))
    return text or None


def _number(value) -> int | float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if isinstance(value, float) and value.is_integer() else value
    match = re.search(r"(-?\d+(?:\.\d+)?)", _blank(value).replace(",", ""))
    if not match:
        return None
    number = float(match.group(1))
    return int(number) if number.is_integer() else number


_MEASUREMENT_ONLY_RE = re.compile(
    r"(?i)^[\d./\s]*(?:m3|cbm|kgs?|pw\s*\d+|cm)(?:[\d./\s]*(?:m3|cbm|kgs?|pw\s*\d+|cm|/))*$"
)
_CARTON_RE = re.compile(r"(?i)\b(\d+(?:\.\d+)?)\s*(?:ctn|ctns|cartons?)\b")
_WEIGHT_RE = re.compile(r"(?i)\b(\d+(?:\.\d+)?)\s*kgs?\b")
_CODE_RE = re.compile(r"(?i)\b([A-Z]{1,3}\s?\d{3,5}|\d{3,5})\b")


def _is_measurement_only(name: str) -> bool:
    text = name.strip()
    if not text:
        return True
    if _MEASUREMENT_ONLY_RE.fullmatch(text):
        return True
    # No letters → not a customer mark
    if not re.search(r"[A-Za-z\u0600-\u06FF]", text):
        return True
    cleaned = _WEIGHT_RE.sub(" ", text)
    cleaned = _CARTON_RE.sub(" ", cleaned)
    cleaned = re.sub(r"(?i)\b(?:m3|cbm|pw\s*\d+|cm)\b", " ", cleaned)
    cleaned = re.sub(r"[\d./]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -/|")
    return not cleaned


def _clean_mark_name(name: str) -> str | None:
    text = name.strip()
    if not text:
        return None
    # Detail line: "HADIA RAY BNLH / 803kgs / 26ctn" → name before weight/ctn
    text = re.split(r"(?i)\s*/\s*\d+(?:\.\d+)?\s*kgs?\b", text, maxsplit=1)[0]
    text = re.split(r"(?i)\s+\d+(?:\.\d+)?\s*kgs?\b", text, maxsplit=1)[0]
    text = re.split(r"(?i)\s*/\s*\d+(?:\.\d+)?\s*(?:ctn|ctns|cartons?)\b", text, maxsplit=1)[0]
    text = re.split(r"(?i)\s+\d+(?:\.\d+)?\s*(?:ctn|ctns|cartons?)\b", text, maxsplit=1)[0]
    text = re.split(r"(?i)\s+\d+(?:\.\d+)?\s*(?:m3|cbm|cm)\b", text, maxsplit=1)[0]
    text = re.split(r"(?i)\s+pw\s*\d+\b", text, maxsplit=1)[0]
    text = re.sub(r"\s+", " ", text).strip(" -|/=")
    if not text or _is_measurement_only(text):
        return None
    return text


def _mark(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    raw_name = _text(raw.get("name")) or ""
    detail = " ".join(
        part
        for part in (
            raw_name,
            _text(raw.get("detail_line")),
            _text(raw.get("raw_line")),
            _text(raw.get("notes")),
        )
        if part
    )
    if not raw_name and not detail:
        return None
    source = detail or raw_name
    if _is_measurement_only(source) and not _text(raw.get("name")):
        return None
    name = _clean_mark_name(raw_name or source)
    if not name:
        return None
    cartons = _number(raw.get("cartons"))
    if cartons is None:
        match = _CARTON_RE.search(source)
        if match:
            cartons = _number(match.group(1))
    weight_kg = _number(raw.get("weight_kg") if raw.get("weight_kg") is not None else raw.get("weight"))
    if weight_kg is None:
        match = _WEIGHT_RE.search(source)
        if match:
            weight_kg = _number(match.group(1))
    customer_code = _text(raw.get("customer_code"))
    if not customer_code:
        code_match = _CODE_RE.search(name)
        if code_match and re.search(r"\d", code_match.group(1)):
            customer_code = re.sub(r"\s+", "", code_match.group(1).upper())
    return {
        "name": name,
        "customer_code": customer_code,
        "mix": _number(raw.get("mix")),
        "cartons": cartons,
        "weight_kg": weight_kg,
        "notes": _text(raw.get("notes")),
    }


def normalize_extract(data: dict) -> dict[str, Any]:
    raw_pallets = data.get("pallets")
    by_side: dict[str, list[dict[str, Any]]] = {"left": [], "right": []}
    if isinstance(raw_pallets, list):
        for index, pallet in enumerate(raw_pallets):
            if not isinstance(pallet, dict):
                continue
            side = (_text(pallet.get("side")) or "").lower()
            if side not in by_side:
                side = "left" if index == 0 else "right" if index == 1 else None
            if side not in by_side:
                continue
            marks: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in pallet.get("marks") or []:
                mark = _mark(item)
                if not mark:
                    continue
                key = mark["name"].casefold()
                if key in seen:
                    continue
                seen.add(key)
                # Default mix from side when missing (circled 1/2 convention)
                if mark["mix"] is None:
                    mark["mix"] = 1 if side == "left" else 2
                marks.append(mark)
            by_side[side] = marks
    issues = []
    raw_issues = data.get("issues")
    if isinstance(raw_issues, list):
        for item in raw_issues:
            text = _text(item)
            if text:
                issues.append(text)
    marks_total = len(by_side["left"]) + len(by_side["right"])
    return {
        "pallets": [
            {"side": "left", "marks": by_side["left"]},
            {"side": "right", "marks": by_side["right"]},
        ],
        "issues": issues,
        "notes": _text(data.get("notes")),
        "readable": bool(data.get("readable", marks_total > 0)),
    }


def normalize_check(data: dict) -> dict[str, Any]:
    def _names(key: str) -> list[str]:
        out: list[str] = []
        raw = data.get(key)
        if not isinstance(raw, list):
            return out
        for item in raw:
            if isinstance(item, dict):
                text = _text(item.get("name") or item.get("plan_name") or item.get("detail"))
            else:
                text = _text(item)
            if text:
                out.append(text)
        return out

    mismatches = []
    raw_mm = data.get("mismatches")
    if isinstance(raw_mm, list):
        for item in raw_mm:
            if not isinstance(item, dict):
                continue
            mismatches.append(
                {
                    "plan_name": _text(item.get("plan_name")),
                    "photo_name": _text(item.get("photo_name")),
                    "detail": _text(item.get("detail")),
                }
            )
    return {
        "ok": bool(data.get("ok")),
        "matched": _names("matched"),
        "missing_from_photos": _names("missing_from_photos"),
        "extra_in_photos": _names("extra_in_photos"),
        "mismatches": mismatches,
        "notes": _text(data.get("notes")),
    }


def _loading_files(db: Session, item_id: int) -> list[CargoFile]:
    return list(
        db.scalars(
            select(CargoFile)
            .where(
                CargoFile.entity_type == LOADING_ENTITY,
                CargoFile.entity_id == str(item_id),
                CargoFile.deleted_at.is_(None),
                CargoFile.kind == "loading",
            )
            .order_by(CargoFile.id.asc())
        ).all()
    )


def _llm_json(
    *,
    prompt_key: str,
    prompt: str,
    user: User,
    entity_id: str,
    files: list[tuple[bytes, str]] | None = None,
    input_extra: dict | None = None,
) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    with Trace(
        prompt_key,
        actor_user_id=user.id,
        entity_type=ENTITY,
        entity_id=entity_id,
        input_json={"prompt": prompt, **(input_extra or {})},
    ) as run:
        text = ""
        for max_tokens in (2048, 8192):
            t0 = time.perf_counter()
            result = generate_content(
                prompt=prompt,
                files=files or [],
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
    return parsed


def flatten_marks(extracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for extract in extracts:
        for pallet in extract.get("pallets") or []:
            if not isinstance(pallet, dict):
                continue
            side = pallet.get("side")
            for mark in pallet.get("marks") or []:
                if not isinstance(mark, dict):
                    continue
                flat.append({**mark, "side": side})
    return flat


def extract_file(
    db: Session,
    loading: ContainerLoading,
    file_row: CargoFile,
    user: User,
    request,
) -> dict[str, Any]:
    path = Path(file_row.stored_path)
    if not path.is_file():
        raise AppError(422, {"message": "Stored photo is missing"})
    if not (file_row.mime or "").startswith("image/"):
        raise AppError(422, {"message": "Only image photos can be extracted"})
    prompt = get_active_prompt("container_loading.photo")
    raw = _llm_json(
        prompt_key="container_loading.photo",
        prompt=prompt,
        user=user,
        entity_id=str(loading.id),
        files=[(path.read_bytes(), file_row.mime)],
        input_extra={"file_id": file_row.id},
    )
    extract = normalize_extract(raw)
    before = file_row.extracted_json
    file_row.extracted_json = extract
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="extract_photo",
        entity_type=ENTITY,
        entity_id=str(loading.id),
        before={"extracted": before},
        after={"file_id": file_row.id, "extracted": extract},
        changed=[
            {
                "field": "extracted",
                "old": None,
                "new": f"file #{file_row.id}: "
                f"{sum(len(p.get('marks') or []) for p in extract.get('pallets') or [])} marks",
            }
        ],
        request=request,
    )
    db.commit()
    db.refresh(file_row)
    return {"item": file_out(file_row), "extracted": extract}


def update_extracted(
    db: Session,
    loading: ContainerLoading,
    file_row: CargoFile,
    body: dict[str, Any],
    user: User,
    request,
) -> dict[str, Any]:
    if loading.deleted_at is not None:
        raise AppError(400, {"message": "Cannot update a deleted row"})
    extract = normalize_extract(body if isinstance(body, dict) else {})
    before = file_row.extracted_json
    file_row.extracted_json = extract
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="update_extract",
        entity_type=ENTITY,
        entity_id=str(loading.id),
        before={"extracted": before},
        after={"file_id": file_row.id, "extracted": extract},
        changed=[{"field": "extracted", "old": "previous", "new": f"edited file #{file_row.id}"}],
        request=request,
    )
    db.commit()
    db.refresh(file_row)
    return {"item": file_out(file_row), "extracted": extract}


def _rollup_summary(files: list[CargoFile]) -> dict[str, Any]:
    extracts = [row.extracted_json for row in files if isinstance(row.extracted_json, dict)]
    marks = flatten_marks(extracts)
    return {
        "photo_count": len(files),
        "extracted_count": len(extracts),
        "mark_count": len(marks),
        "marks": marks,
    }


def run_plan_check(
    db: Session,
    loading: ContainerLoading,
    user: User,
    request,
    *,
    force: bool = False,
) -> dict[str, Any]:
    files = _loading_files(db, loading.id)
    if not files:
        raise AppError(422, {"message": "Upload at least one photo first"})

    extracted_items = []
    for file_row in files:
        if force or not isinstance(file_row.extracted_json, dict):
            extract_file(db, loading, file_row, user, request)
            db.refresh(file_row)
        extracted_items.append({"file_id": file_row.id, "extracted": file_row.extracted_json})

    files = _loading_files(db, loading.id)
    summary = _rollup_summary(files)
    loading.summary_json = summary
    check: dict[str, Any] | None = None
    if loading.plan_json and isinstance(loading.plan_json, dict):
        plan_payload = {
            "container_number": loading.plan_json.get("container_number"),
            "lines": loading.plan_json.get("lines") or [],
        }
        photo_payload = {
            "marks": summary["marks"],
            "by_file": extracted_items,
        }
        prompt = get_active_prompt("container_loading.check")
        check_prompt = (
            f"{prompt}\n\nLOADING_PLAN_JSON:\n{json.dumps(plan_payload, ensure_ascii=False)}\n\n"
            f"PHOTO_EXTRACTS_JSON:\n{json.dumps(photo_payload, ensure_ascii=False)}"
        )
        raw = _llm_json(
            prompt_key="container_loading.check",
            prompt=check_prompt,
            user=user,
            entity_id=str(loading.id),
            files=None,
            input_extra={"plan_lines": len(plan_payload["lines"]), "mark_count": len(summary["marks"])},
        )
        check = normalize_check(raw)
        loading.check_json = check
        write_audit(
            db,
            actor_user_id=user.id,
            action="check_plan",
            entity_type=ENTITY,
            entity_id=str(loading.id),
            before=None,
            after={"check": check},
            changed=[
                {
                    "field": "check",
                    "old": None,
                    "new": "ok" if check.get("ok") else f"missing {len(check.get('missing_from_photos') or [])}",
                }
            ],
            request=request,
        )
    else:
        loading.check_json = None

    loading.updated_at = datetime.now(timezone.utc)
    loading.updated_by = user.id
    db.commit()
    db.refresh(loading)
    return {
        "item": loading_out(
            loading,
            file_count=counts_for(db, LOADING_ENTITY, [loading.id]).get(loading.id, 0),
        ),
        "summary": summary,
        "check": check,
        "plan_required": loading.plan_json is None,
    }


def require_loading_file(db: Session, item_id: int, file_id: int, user: User) -> tuple[ContainerLoading, CargoFile]:
    from app.container_loading import get_row

    loading = get_row(db, item_id, user)
    file_row = get_file(db, LOADING_ENTITY, item_id, file_id)
    if file_row.deleted_at is not None and user.role != "admin":
        raise AppError(404, {"message": "File not found"})
    return loading, file_row
