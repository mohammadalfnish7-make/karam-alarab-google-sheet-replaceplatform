import base64
import json
import re

import httpx

from app.config import settings
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
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Extraction JSON must be an object")
    return data


def _reply_text(body: dict) -> tuple[str, str]:
    candidates = body.get("candidates") or []
    if not candidates:
        return "", ""
    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts") or []
    visible = [part for part in parts if isinstance(part, dict) and not part.get("thought")]
    chosen = visible or [part for part in parts if isinstance(part, dict)]
    text = "\n".join(part.get("text", "") for part in chosen)
    return text, str(candidate.get("finishReason") or "")


def _ask(file_bytes: bytes, mime: str, prompt: str, max_tokens: int) -> dict:
    model = settings.gemini_model.strip() or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime,
                            "data": base64.b64encode(file_bytes).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    try:
        response = httpx.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key.strip()},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise AppError(
            502,
            {"message": f"Gemini request failed: {exc}", "field_errors": {}, "warnings": []},
        ) from exc


def read_check_file(file_bytes: bytes, mime: str, kind: str) -> dict:
    if not settings.gemini_api_key.strip():
        raise AppError(
            503,
            {
                "message": "GEMINI_API_KEY is not configured. The PDF is stored; extraction was not run.",
                "field_errors": {},
                "warnings": [],
            },
        )
    prompt = SCALE_PROMPT if kind == "scale" else NOTE_PROMPT
    text = ""
    for max_tokens in (2048, 8192):
        reply, finish = _reply_text(_ask(file_bytes, mime, prompt, max_tokens))
        text = reply
        if not text.strip():
            continue
        try:
            return normalize_check(kind, _object(text))
        except (json.JSONDecodeError, ValueError):
            if finish != "MAX_TOKENS":
                break
    raise AppError(422, {"message": "Could not read this file. Try again.", "field_errors": {}, "warnings": []})
