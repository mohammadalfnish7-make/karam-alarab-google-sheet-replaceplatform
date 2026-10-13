import base64
import json
import re

import httpx

from app.config import settings
from app.constants import AIR_STATUSES, EXIT_STATUSES, SEA_STAGES, SHIPPING_ROUTES
from app.errors import AppError


def extraction_prompt(target: str, filename: str = "") -> str:
    file_note = ""
    if filename.strip():
        file_note = (
            f" The uploaded filename is {filename.strip()!r}. "
            "If that name contains TL followed by digits, those digits are the customer mark "
            "when the printed mark is unclear."
        )
    if target == "exit":
        return (
            "Extract every goods row from this PDF into a JSON array. "
            "Return only JSON, no markdown. Each object uses these keys: "
            "mark, supplier, invoice_no, cartons, date_of_submission, status. "
            "mark is the TL customer mark as digits only: TL4455, TL-4455, and TL 4455 all become 4455. "
            "Dates are YYYY-MM-DD or null. cartons is an integer count of cartons, CTN, or boxes, not pieces. "
            f"status is one of {EXIT_STATUSES} or null. "
            "Do not invent a row number. Do not invent rows that are not in the document. "
            "Use null for missing values."
            + file_note
        )
    cargo = (
        "This PDF is a supplier file for one shipment. It may contain a delivery note, a packing list, "
        "and a tax invoice, including scanned pages. Return a JSON array with one object for the whole "
        "shipment. Do not return one object per product, perfume, or invoice line. "
        "Return only JSON, no markdown. "
        "customer_code is the TL mark as digits only. TL4455, TL-4455, and TL 4455 all become 4455. "
        "Read it from a MARK column or a TL mark printed on the delivery note. "
        "company_name is the supplier or vendor that issued the document, usually the heading company. "
        "Do not use the buyer when the buyer is Karam Al Arab or Karam Al Oud. "
        "cartons is the integer count of cartons, CTN, or boxes. "
        "A line that says 6 CTN, or boxes numbered BOX-1 through BOX-6, means 6. "
        "Do not use piece counts such as PCS. "
        "gross_weight_kg is the total weight in kilograms as a number, without the KG unit. "
        "If the packing list has one WEIGHT column and a single total, put that total in gross_weight_kg. "
        "net_weight_kg is the net weight in kilograms only when the document prints net separately from gross. "
        "If only one weight is printed, net_weight_kg is null. "
        "If the document says NO PALLET, set gross_is_no_pallet true and gross_weight_kg null. "
        "Otherwise gross_is_no_pallet is false. "
        "system_code is printed text that is DL followed by digits, or null. Do not invent a system code. "
        "date_received is YYYY-MM-DD only when the document labels a received date. "
        "Do not copy the invoice date or the packing-list date into date_received. "
        "Use null for anything that is not printed."
        + file_note
    )
    if target == "air":
        return (
            cargo
            + " shipment_number is printed text that is AR followed by digits, or null. "
            "A supplier invoice number is not a shipment number. "
            f"status is one of {AIR_STATUSES} or null. "
            "Each object uses these keys: "
            "date_received, customer_code, company_name, cartons, gross_weight_kg, "
            "gross_is_no_pallet, net_weight_kg, system_code, shipment_number, status."
        )
    return (
        cargo
        + " shipment_number is printed text that is D followed by digits, or null. "
        "A supplier invoice number is not a shipment number. "
        f"shipping_route is one of {SHIPPING_ROUTES} or null. "
        f"stage is one of {SEA_STAGES} or null. "
        "Each object uses these keys: "
        "date_received, customer_code, company_name, cartons, gross_weight_kg, "
        "gross_is_no_pallet, net_weight_kg, system_code, shipment_number, shipping_route, stage."
    )


def _text(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    return str(value).strip()


def _mark_digits(value: str) -> str:
    match = re.search(r"TL[-\s]*([0-9]+)", value, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    if re.fullmatch(r"[0-9]+", value):
        return value
    return ""


def _filename_mark(filename: str) -> str:
    match = re.search(r"TL[-\s]*([0-9]+)", filename or "", flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _customer_code(value, filename: str):
    printed = _mark_digits(_text(value))
    from_name = _filename_mark(filename)
    if from_name and (not printed or (from_name.startswith(printed) and len(from_name) > len(printed))):
        return from_name
    if printed:
        return printed
    text = _text(value)
    return text or None


def _cartons(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = _text(value)
    match = re.search(r"(\d+)\s*(?:CTNS?|CARTONS?|BOXES?)\b", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    if re.fullmatch(r"\d+", text):
        return int(text)
    return value


def _weight(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = _text(value).replace(",", "")
    if re.fullmatch(r"NO\s*PALLETS?", text, flags=re.IGNORECASE):
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:KG|KGS)?", text, flags=re.IGNORECASE)
    if match:
        number = float(match.group(1))
        return int(number) if number.is_integer() else number
    return value


def _no_pallet(value, gross) -> bool:
    if isinstance(value, bool):
        flagged = value
    else:
        flagged = bool(re.fullmatch(r"NO\s*PALLETS?", _text(value), flags=re.IGNORECASE))
    gross_text = _text(gross)
    return flagged or bool(re.fullmatch(r"NO\s*PALLETS?", gross_text, flags=re.IGNORECASE))


def _coded(value, pattern: str):
    compact = re.sub(r"\s+", "", _text(value)).upper()
    if re.fullmatch(pattern, compact):
        return compact
    return None


def normalize_extracted_row(target: str, row, filename: str = ""):
    """Keep sheet fields and drop values the supplier PDF does not actually print."""
    if not isinstance(row, dict):
        return row
    cleaned = dict(row)
    if target == "exit":
        cleaned["mark"] = _customer_code(row.get("mark"), filename)
        cleaned["cartons"] = _cartons(row.get("cartons"))
        return cleaned

    no_pallet = _no_pallet(row.get("gross_is_no_pallet"), row.get("gross_weight_kg"))
    cleaned["customer_code"] = _customer_code(row.get("customer_code"), filename)
    company = re.sub(r"\s+", " ", _text(row.get("company_name")))
    cleaned["company_name"] = company or None
    cleaned["cartons"] = _cartons(row.get("cartons"))
    cleaned["gross_is_no_pallet"] = no_pallet
    cleaned["gross_weight_kg"] = None if no_pallet else _weight(row.get("gross_weight_kg"))
    cleaned["net_weight_kg"] = _weight(row.get("net_weight_kg"))
    cleaned["system_code"] = _coded(row.get("system_code"), r"DL[0-9]+")
    shipment_pattern = r"AR[0-9]+" if target == "air" else r"D[0-9]+"
    cleaned["shipment_number"] = _coded(row.get("shipment_number"), shipment_pattern)
    received = _text(row.get("date_received"))
    cleaned["date_received"] = received or None
    return cleaned


def parse_model_json(text: str):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("The model did not return JSON") from exc
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        data = data["rows"]
    if not isinstance(data, list):
        raise ValueError("Extraction JSON must be an array of rows")
    return data


def gemini_extract(pdf_bytes: bytes, target: str, filename: str = "") -> str:
    if not settings.gemini_api_key.strip():
        raise AppError(
            503,
            {
                "message": "GEMINI_API_KEY is not configured. The PDF is stored; extraction was not run.",
                "field_errors": {},
                "warnings": [],
            },
        )
    model = settings.gemini_model.strip() or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": extraction_prompt(target, filename)},
                    {
                        "inlineData": {
                            "mimeType": "application/pdf",
                            "data": base64.b64encode(pdf_bytes).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192,
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
        body = response.json()
    except httpx.HTTPError as exc:
        raise AppError(
            502,
            {"message": f"Gemini request failed: {exc}", "field_errors": {}, "warnings": []},
        ) from exc
    candidates = body.get("candidates") or []
    parts = []
    if candidates:
        parts = candidates[0].get("content", {}).get("parts") or []
    text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not text.strip():
        return json.dumps(body)
    return text
