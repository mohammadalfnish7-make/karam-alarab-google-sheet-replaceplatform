import hashlib
import json
import re
import time

from app.agents.llm import generate_content, model_name, provider
from app.agents.trace import Trace
from app.errors import AppError

NOTE_PROMPT = (
    "Read this delivery note. Return one JSON object using only values printed on the page. "
    "Keys: company_name, date, mark, cartons, goods, party. "
    "company_name is the company that issued the note, usually the heading. "
    "Do not use the buyer when the buyer is Karam. "
    "date is YYYY-MM-DD or null. "
    "mark is the MARK value as printed, including a TL prefix. Do not shorten the digits. "
    "cartons is the integer carton count from CTN or boxes, not a piece count, or null. "
    "goods is the goods description or null. "
    "party is the party or shipper printed on the note, or null. "
    "Use null when a value is not printed."
)

SCALE_PROMPT = (
    "Read this photo of goods on a weighing scale. Return one JSON object using only values you can see. "
    "Keys: mark, cartons, total_weight_kg, pallet_weight_kg, scale_weight_kg. "
    "mark is the handwritten TL mark as written. Do not shorten the digits. "
    "cartons is the handwritten carton count, an integer or null. "
    "total_weight_kg is the handwritten total weight labeled TW, in kilograms, or null. "
    "pallet_weight_kg is the handwritten pallet weight labeled PW, in kilograms, or null. "
    "scale_weight_kg is the number shown on the digital scale display, in kilograms, or null. "
    "Do not calculate a net weight. Use null when a value is not visible."
)

_MONTHS = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def _blank(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    return str(value).strip()


def _date(value):
    text = _blank(value)
    if not text:
        return None
    numeric = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if numeric:
        return f"{numeric.group(1)}-{int(numeric.group(2)):02d}-{int(numeric.group(3)):02d}"
    numeric = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", text)
    if numeric:
        year = numeric.group(3)
        if len(year) == 2:
            year = "20" + year
        return f"{year}-{int(numeric.group(2)):02d}-{int(numeric.group(1)):02d}"
    named = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if named:
        month = _MONTHS.get(named.group(2)[:3].lower())
        if month:
            return f"{named.group(3)}-{month}-{int(named.group(1)):02d}"
    return text


def _cartons(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    match = re.search(r"(\d+)", _blank(value))
    return int(match.group(1)) if match else None


def _weight(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value
    match = re.search(r"(\d+(?:\.\d+)?)", _blank(value).replace(" ", ""))
    if not match:
        return None
    number = float(match.group(1))
    return int(number) if number.is_integer() else number


def _text(value):
    text = re.sub(r"\s+", " ", _blank(value))
    return text or None


def normalize_check(kind: str, data: dict) -> dict:
    if kind == "scale":
        return {
            "mark": _text(data.get("mark")),
            "cartons": _cartons(data.get("cartons")),
            "total_weight_kg": _weight(data.get("total_weight_kg")),
            "pallet_weight_kg": _weight(data.get("pallet_weight_kg")),
            "scale_weight_kg": _weight(data.get("scale_weight_kg")),
        }
    return {
        "company_name": _text(data.get("company_name")),
        "date": _date(data.get("date")),
        "mark": _text(data.get("mark")),
        "cartons": _cartons(data.get("cartons")),
        "goods": _text(data.get("goods")),
        "party": _text(data.get("party")),
    }


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
        raise ValueError("Extraction JSON must be an object")
    return data


def read_check_file(file_bytes: bytes, mime: str, kind: str, *, actor_user_id: int | None = None) -> dict:
    prompt = SCALE_PROMPT if kind == "scale" else NOTE_PROMPT
    with Trace(
        f"intake.{kind}",
        actor_user_id=actor_user_id,
        input_json={
            "kind": kind,
            "mime": mime,
            "byte_size": len(file_bytes),
            "sha256": hashlib.sha256(file_bytes).hexdigest(),
            "prompt": prompt,
        },
    ) as run:
        text = ""
        budgets = (2048, 8192)
        for max_tokens in budgets:
            t0 = time.perf_counter()
            result = generate_content(
                prompt=prompt,
                file_bytes=file_bytes,
                mime=mime,
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
                fields = normalize_check(kind, _object(text))
                parse_ms = max(0, int((time.perf_counter() - t1) * 1000))
            except (json.JSONDecodeError, ValueError) as exc:
                run.step("parse", input={"finish": finish}, error=str(exc), duration_ms=0)
                if finish.upper() not in {"MAX_TOKENS", "LENGTH"}:
                    break
                continue
            run.step("parse", output=fields, duration_ms=parse_ms)
            run.pending_output = fields
            return fields
        run.pending_output = {"text": text}
        raise AppError(422, {"message": "Could not read this file. Try again.", "field_errors": {}, "warnings": []})
