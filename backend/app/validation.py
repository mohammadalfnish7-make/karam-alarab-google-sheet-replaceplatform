"""Create and update rules for sea, air, and exit rows.

Legacy rows keep a stored value that no longer matches the rules until that
field is changed. New values are checked in full.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import AIR_STATUSES, DEFAULT_SEA_STAGE, EXIT_STATUSES, SEA_STAGES
from app.models import AirCargo, Company, Customer, SeaCargo, Supplier


def looks_real(value: str | None) -> bool:
    if not value:
        return False
    return any(ch.isalnum() for ch in value)


def parse_dmy(text: str) -> date | None:
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text.strip())
    if not match:
        return None
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_compact_dmy(text: str) -> date | None:
    """1107/2026 is 11/07/2026 with the first slash missing."""
    match = re.fullmatch(r"(\d{2})(\d{2})/(\d{4})", text.strip())
    if not match:
        return None
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


_INVOICE_TOKEN = re.compile(r"^[A-Za-z]*\d{3,}[A-Za-z]?$")
_INVOICE_YEAR = re.compile(r"^(\d{4}/)(\d{3,})$")


def split_invoices(value: str | None) -> list[str]:
    """Turn one sheet cell into each invoice number it lists.

    A shared year prefix is copied onto each tail: 2026/00104-00105 becomes
    2026/00104 and 2026/00105. A code that uses a dash inside one number,
    such as SL-22891-26 or 013-26, stays one invoice.
    """
    if not value or not str(value).strip():
        return []
    chunks = re.split(r"[\n,;]+|\s*/\s+|\s+/\s*", str(value).replace("\r", "\n"))
    numbers: list[str] = []
    for chunk in chunks:
        chunk = re.sub(r"\s+", " ", chunk).strip(" -/;")
        if not chunk:
            continue
        for piece in _slash_invoices(chunk):
            numbers.extend(_expand_invoice_chunk(piece))
    seen: set[str] = set()
    unique: list[str] = []
    for number in numbers:
        key = number.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(number)
    return unique


def _slash_invoices(chunk: str) -> list[str]:
    if _INVOICE_YEAR.match(chunk):
        return [chunk]
    parts = [part.strip() for part in chunk.split("/") if part.strip()]
    if len(parts) >= 2 and all(_INVOICE_TOKEN.match(part) for part in parts):
        return parts
    return [chunk]


def _expand_invoice_chunk(chunk: str) -> list[str]:
    parts = [part.strip() for part in chunk.split("-") if part.strip()]
    if len(parts) < 2:
        return [chunk]
    year = _INVOICE_YEAR.match(parts[0])
    if year and all(re.fullmatch(r"\d{3,}", part) for part in parts[1:]):
        prefix = year.group(1)
        return [parts[0], *[prefix + part for part in parts[1:]]]
    if all(_INVOICE_TOKEN.match(part) for part in parts):
        return parts
    return [chunk]


def bring_date_not_after_today(value: date, today: date | None = None) -> date:
    """Sheet dates after today are a day/month swap or a year filled down from 2026."""
    today = today or date.today()
    if value <= today:
        return value
    if value.day <= 12:
        try:
            swapped = date(value.year, value.day, value.month)
        except ValueError:
            swapped = None
        if swapped is not None and swapped <= today:
            value = swapped
    if value > today and value.year > today.year:
        try:
            pulled = date(today.year, value.month, value.day)
        except ValueError:
            pulled = None
        if pulled is not None and pulled <= today:
            return pulled
    return value


def excel_serial_to_date(serial: int) -> date | None:
    # Excel's day 1 is 1899-12-31, with the 1900 leap-year bug. 1899-12-30 is the
    # epoch that converts serial numbers onto real calendar dates.
    if serial < 1 or serial > 100000:
        return None
    parsed = date(1899, 12, 30) + timedelta(days=serial)
    if parsed.year < 2000 or parsed.year > 2100:
        return None
    return parsed


def canonical_choice(value: str, options: list[str]) -> str | None:
    text = re.sub(r"\s+", " ", value.strip())
    for option in options:
        if text == option or text.lower() == option.lower():
            return option
    return None


def canonical_stage(value: str) -> str | None:
    text = re.sub(r"\s+", " ", value.strip())
    compact = re.sub(r"\s+", "", text).upper().replace("📦", "")
    if compact == "STAGE2":
        return "STAGE 2"
    if compact == "WH":
        return DEFAULT_SEA_STAGE
    return canonical_choice(text, SEA_STAGES)


def canonical_exit_status(value: str) -> str | None:
    text = value.strip()
    if text.upper() == "PENDING":
        return "Pending"
    return canonical_choice(text, EXIT_STATUSES)


def same(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if isinstance(left, datetime):
        left = left.date()
    if isinstance(right, datetime):
        right = right.date()
    if isinstance(left, (Decimal, float)) or isinstance(right, (Decimal, float)):
        try:
            return abs(float(left) - float(right)) < 1e-6
        except (TypeError, ValueError):
            return False
    return left == right


def as_text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        text = str(value).strip()
        return text or None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        return text or None
    text = str(value).strip()
    return text or None


def warning(code: str, field_name: str, message: str) -> dict[str, str]:
    return {"code": code, "field": field_name, "message": message}


def normalize_sea_shipment(raw: str) -> tuple[str, str | None]:
    """Store sea shipment numbers as D plus the digits the user typed.

    Digits alone, ``D45``, ``d45``, and ``D 45`` all become ``D45``.
    Leading zeros are kept. Other prefixes, including DR, are rejected.
    """
    compact = re.sub(r"\s+", "", raw).upper()
    if compact.startswith("DR"):
        return compact, "Shipment numbers cannot use the DR prefix"
    if re.fullmatch(r"[0-9]+", compact):
        return "D" + compact, None
    if re.fullmatch(r"D[0-9]+", compact):
        return compact, None
    return compact, "Sea shipment number must look like D followed by digits"


def next_sea_shipment(db: Session) -> dict[str, Any]:
    """Next sea number is one more than the highest live D+digits value.

    Empty rows, deleted rows, and values that are not D followed by digits
    are ignored. The sequence may have gaps. When nothing matches, start at D1.
    """
    stored = db.scalars(
        select(SeaCargo.shipment_number).where(
            SeaCargo.deleted_at.is_(None),
            SeaCargo.shipment_number.is_not(None),
        )
    )
    highest = 0
    for value in stored:
        if not value:
            continue
        match = re.fullmatch(r"D([0-9]+)", value.strip().upper())
        if not match:
            continue
        number = int(match.group(1))
        if number > highest:
            highest = number
    number = highest + 1
    return {"shipment_number": f"D{number}", "number": number}


@dataclass
class ValidationResult:
    values: dict[str, Any]
    field_errors: dict[str, str] = field(default_factory=dict)
    warnings: list[dict[str, str]] = field(default_factory=list)
    proposed: dict[str, str] = field(default_factory=dict)
    code: str | None = None
    insert_customer: str | None = None
    insert_company: str | None = None
    insert_supplier: str | None = None

    def payload(self, **extra: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "field_errors": self.field_errors,
            "warnings": self.warnings,
        }
        if self.code:
            body["code"] = self.code
        if self.proposed:
            body["proposed"] = self.proposed
        body.update(extra)
        return body


def parse_api_date(value: Any) -> tuple[date | None, str | None]:
    if value is None or value == "":
        return None, None
    if isinstance(value, datetime):
        return value.date(), None
    if isinstance(value, date):
        return value, None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = excel_serial_to_date(int(value))
        return (parsed, None) if parsed else (None, "Invalid date")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None, None
        if re.fullmatch(r"\d+", text):
            parsed = excel_serial_to_date(int(text))
            return (parsed, None) if parsed else (None, "Invalid date")
        iso_candidate = text[:10]
        try:
            return date.fromisoformat(iso_candidate), None
        except ValueError:
            pass
        parsed = parse_dmy(text)
        if parsed:
            return parsed, None
        return None, "Invalid date"
    return None, "Invalid date"


def parse_int(value: Any) -> tuple[int | None, str | None]:
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        return None, "must be an integer"
    if isinstance(value, int):
        return value, None
    if isinstance(value, float):
        if value.is_integer():
            return int(value), None
        return None, "must be a whole number"
    if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        return int(value.strip()), None
    return None, "must be an integer"


def parse_number(value: Any) -> tuple[float | None, str | None]:
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        return None, "must be a number"
    if isinstance(value, Decimal):
        return float(value), None
    if isinstance(value, (int, float)):
        return float(value), None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if re.fullmatch(r"-?\d+(\.\d+)?", text):
            return float(text), None
        return None, "must be a number"
    return None, "must be a number"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "yes", "YES"):
        return True
    return False


def resolve_gross(data: dict[str, Any]) -> tuple[float | None, bool, str | None]:
    gross_token = data.get("gross")
    if gross_token not in (None, ""):
        if isinstance(gross_token, str) and gross_token.strip().upper() in {"NO PALLET", "NO PALLETT"}:
            return None, True, None
        number, error = parse_number(gross_token)
        if error or number is None:
            return None, False, "Gross weight must be a number or NO PALLET"
        if number < 0:
            return None, False, "Gross weight must be 0 or greater"
        return number, False, None

    raw_weight = data.get("gross_weight_kg")
    if isinstance(raw_weight, str) and raw_weight.strip().upper() in {"NO PALLET", "NO PALLETT"}:
        return None, True, None

    no_pallet = _as_bool(data.get("gross_is_no_pallet"))
    weight, error = parse_number(raw_weight)
    if error:
        return None, False, "Gross weight must be a number or NO PALLET"
    if weight is not None and weight < 0:
        return None, False, "Gross weight must be 0 or greater"
    # No pallet may still carry a gross/scale weight; net is expected to match gross.
    if no_pallet:
        return weight, True, None
    if weight is None:
        return None, False, None
    return weight, False, None


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _find_ci(db: Session, model, column, value: str):
    return db.scalar(select(model).where(func.lower(column) == value.lower()))


def system_code_taken(db: Session, code: str, sea_id: int | None, air_id: int | None) -> bool:
    sea_stmt = select(SeaCargo.id).where(SeaCargo.system_code == code, SeaCargo.deleted_at.is_(None))
    if sea_id is not None:
        sea_stmt = sea_stmt.where(SeaCargo.id != sea_id)
    if db.scalar(sea_stmt) is not None:
        return True
    air_stmt = select(AirCargo.id).where(AirCargo.system_code == code, AirCargo.deleted_at.is_(None))
    if air_id is not None:
        air_stmt = air_stmt.where(AirCargo.id != air_id)
    return db.scalar(air_stmt) is not None


def _finish(values, errors, warnings, proposed, insert_customer=None, insert_company=None, insert_supplier=None):
    return ValidationResult(
        values=values,
        field_errors=errors,
        warnings=warnings,
        proposed=proposed,
        code="NEW_VALUE_CONFIRMATION_REQUIRED" if proposed else None,
        insert_customer=insert_customer,
        insert_company=insert_company,
        insert_supplier=insert_supplier,
    )


def validate_cargo(
    db: Session,
    kind: str,
    data: dict[str, Any],
    existing: Any | None,
    *,
    confirm_new_customer: bool,
    confirm_new_company: bool,
) -> ValidationResult:
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    warnings: list[dict[str, str]] = []
    proposed: dict[str, str] = {}
    insert_customer = None
    insert_company = None

    def legacy_keep(field_name: str) -> bool:
        return (
            existing is not None
            and bool(getattr(existing, "legacy", False))
            and same(getattr(existing, field_name, None), values.get(field_name))
        )

    def unchanged(field_name: str) -> bool:
        return existing is not None and same(getattr(existing, field_name, None), values.get(field_name))

    def add_error(field_name: str, message: str, *, force: bool = False) -> None:
        if not force and legacy_keep(field_name):
            return
        errors[field_name] = message

    parsed_date, date_error = parse_api_date(data.get("date_received"))
    if date_error:
        values["date_received"] = getattr(existing, "date_received", None) if existing else None
        add_error("date_received", date_error, force=True)
    else:
        values["date_received"] = parsed_date
        if parsed_date is None:
            warnings.append(warning("DATE_RECEIVED_BLANK", "date_received", "Date received is blank"))
        elif parsed_date > date.today():
            add_error("date_received", "Date is after today")

    customer = as_text(data.get("customer_code"))
    values["customer_code"] = customer
    if customer and not looks_real(customer):
        add_error("customer_code", "Customer code cannot be only dots or punctuation")

    company = as_text(data.get("company_name"))
    values["company_name"] = company
    if not company:
        add_error("company_name", "Company name is required")
    elif not looks_real(company):
        add_error("company_name", "Company name cannot be only dots or punctuation")

    cartons, carton_error = parse_int(data.get("cartons"))
    if carton_error:
        values["cartons"] = getattr(existing, "cartons", None) if existing else None
        add_error("cartons", f"Cartons {carton_error}", force=True)
    else:
        values["cartons"] = cartons
        if cartons is None:
            add_error("cartons", "Cartons is required and must be greater than 0")
        elif cartons <= 0:
            add_error("cartons", "Cartons must be an integer greater than 0")

    weight, no_pallet, gross_error = resolve_gross(data)
    values["gross_weight_kg"] = weight
    values["gross_is_no_pallet"] = no_pallet
    if gross_error:
        add_error("gross_weight_kg", gross_error, force=True)

    net, net_error = parse_number(data.get("net_weight_kg"))
    if net_error:
        values["net_weight_kg"] = getattr(existing, "net_weight_kg", None) if existing else None
        add_error("net_weight_kg", f"Net weight {net_error}", force=True)
    else:
        values["net_weight_kg"] = net
        if net is not None and net < 0:
            add_error("net_weight_kg", "Net weight must be 0 or greater")
        elif (
            net is not None
            and weight is not None
            and not no_pallet
            and net > weight
            and "net_weight_kg" not in errors
            and "gross_weight_kg" not in errors
        ):
            warnings.append(warning("NET_EXCEEDS_GROSS", "net_weight_kg", "Net weight is greater than gross weight"))

    system = as_text(data.get("system_code"))
    if not system:
        # Optional on create — usually filled later from Zokhar upload.
        values["system_code"] = None
    elif re.fullmatch(r"DL[0-9]+", system, flags=re.IGNORECASE):
        values["system_code"] = "DL" + system[2:]
    else:
        values["system_code"] = system
        add_error("system_code", "System code must look like DL followed by digits")

    shipment = as_text(data.get("shipment_number"))
    if not shipment:
        values["shipment_number"] = None
        warnings.append(warning("SHIPMENT_BLANK", "shipment_number", "Shipment number is blank"))
    elif kind == "sea":
        normalized, shipment_error = normalize_sea_shipment(shipment)
        values["shipment_number"] = normalized
        if shipment_error:
            add_error("shipment_number", shipment_error)
    else:
        shipment_up = shipment.upper()
        values["shipment_number"] = shipment_up
        if not re.fullmatch(r"AR[0-9]+", shipment_up):
            add_error("shipment_number", "Air shipment number must look like AR followed by digits")

    if kind == "sea":
        route = as_text(data.get("shipping_route"))
        if not route:
            values["shipping_route"] = None
            warnings.append(warning("ROUTE_BLANK", "shipping_route", "Shipping route is blank"))
        else:
            token = re.sub(r"\s+", " ", route).upper()
            if token == "TURKY":
                token = "TURKEY"
            values["shipping_route"] = token
            if token == "IRAN TRANSIT":
                add_error("shipping_route", "IRAN TRANSIT is not an allowed route")
            elif token not in {"IRAN", "TURKEY"}:
                add_error("shipping_route", "Route must be IRAN or TURKEY")
        stage_raw = data.get("stage")
        if stage_raw is None or (isinstance(stage_raw, str) and not stage_raw.strip()):
            values["stage"] = DEFAULT_SEA_STAGE
        else:
            stage_text = str(stage_raw).strip()
            canon = canonical_stage(stage_text)
            values["stage"] = canon or stage_text
            if canon is None:
                add_error("stage", "Stage is not an allowed value")
        values["status"] = None
    else:
        values["shipping_route"] = None
        values["stage"] = None
        status_raw = data.get("status")
        if status_raw is None or (isinstance(status_raw, str) and not status_raw.strip()):
            values["status"] = None
        else:
            status_text = str(status_raw).strip()
            canon = canonical_choice(status_text, AIR_STATUSES)
            values["status"] = canon or status_text
            if canon is None:
                add_error("status", "Status must be AT AIRPORT or delivered to customer✅")

    if customer and "customer_code" not in errors and looks_real(customer):
        found = _find_ci(db, Customer, Customer.code, customer)
        if found:
            if not unchanged("customer_code"):
                values["customer_code"] = found.code
        elif not unchanged("customer_code"):
            if not confirm_new_customer:
                add_error("customer_code", "New customer code needs confirmation")
                proposed["customer_code"] = customer
            else:
                insert_customer = customer

    if company and "company_name" not in errors and looks_real(company):
        found = _find_ci(db, Company, Company.name, company)
        if found:
            if not unchanged("company_name"):
                values["company_name"] = found.name
        elif not unchanged("company_name"):
            if not confirm_new_company:
                add_error("company_name", "New company name needs confirmation")
                proposed["company_name"] = company
            else:
                insert_company = company

    system_code = values.get("system_code")
    if "system_code" not in errors and system_code and re.fullmatch(r"DL[0-9]+", system_code):
        sea_id = existing.id if existing is not None and kind == "sea" else None
        air_id = existing.id if existing is not None and kind == "air" else None
        if system_code_taken(db, system_code, sea_id, air_id):
            warnings.append(
                warning(
                    "SYSTEM_CODE_DUPLICATE",
                    "system_code",
                    "System code already exists on another sea or air row",
                )
            )
        customer_digits = _digits(values.get("customer_code") or "")
        system_digits = system_code[2:]
        if customer_digits and system_digits.isdigit() and int(system_digits) == int(customer_digits):
            warnings.append(
                warning(
                    "SYSTEM_CODE_MATCHES_CUSTOMER",
                    "system_code",
                    "System code number matches the customer code",
                )
            )

    return _finish(values, errors, warnings, proposed, insert_customer, insert_company)


def validate_exit(
    db: Session,
    data: dict[str, Any],
    existing: Any | None,
    *,
    confirm_new_customer: bool,
    confirm_new_supplier: bool,
) -> ValidationResult:
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    warnings: list[dict[str, str]] = []
    proposed: dict[str, str] = {}
    insert_customer = None
    insert_supplier = None

    def legacy_keep(field_name: str) -> bool:
        return (
            existing is not None
            and bool(getattr(existing, "legacy", False))
            and same(getattr(existing, field_name, None), values.get(field_name))
        )

    def unchanged(field_name: str) -> bool:
        return existing is not None and same(getattr(existing, field_name, None), values.get(field_name))

    def add_error(field_name: str, message: str, *, force: bool = False) -> None:
        if not force and legacy_keep(field_name):
            return
        errors[field_name] = message

    mark = as_text(data.get("mark"))
    values["mark"] = mark
    if mark and not looks_real(mark):
        add_error("mark", "Mark cannot be only dots or punctuation")

    supplier = as_text(data.get("supplier"))
    values["supplier"] = supplier
    if not supplier:
        add_error("supplier", "Supplier is required")
    elif not looks_real(supplier):
        add_error("supplier", "Supplier cannot be only dots or punctuation")

    numbers: list[str] = []
    raw_numbers = data.get("invoice_numbers")
    if isinstance(raw_numbers, list) and any(as_text(item) for item in raw_numbers):
        for item in raw_numbers:
            numbers.extend(split_invoices(as_text(item)))
    else:
        numbers = split_invoices(as_text(data.get("invoice_no")))
    seen: set[str] = set()
    invoice_numbers: list[str] = []
    for number in numbers:
        key = number.lower()
        if key in seen:
            continue
        seen.add(key)
        invoice_numbers.append(number)
    values["invoice_numbers"] = invoice_numbers
    values["invoice_no"] = ", ".join(invoice_numbers) if invoice_numbers else None
    if not invoice_numbers:
        warnings.append(warning("INVOICE_BLANK", "invoice_no", "Invoice number is blank"))

    cartons, carton_error = parse_int(data.get("cartons"))
    if carton_error:
        values["cartons"] = getattr(existing, "cartons", None) if existing else None
        add_error("cartons", f"Cartons {carton_error}", force=True)
    else:
        values["cartons"] = cartons
        if cartons is None:
            warnings.append(warning("CARTONS_BLANK", "cartons", "Cartons is blank"))
        elif cartons <= 0:
            add_error("cartons", "Cartons must be an integer greater than 0")

    parsed_date, date_error = parse_api_date(data.get("date_of_submission"))
    if date_error:
        values["date_of_submission"] = getattr(existing, "date_of_submission", None) if existing else None
        add_error("date_of_submission", date_error, force=True)
    else:
        values["date_of_submission"] = parsed_date
        if parsed_date is None:
            warnings.append(
                warning("DATE_OF_SUBMISSION_BLANK", "date_of_submission", "Date of submission is blank")
            )
        elif parsed_date > date.today():
            add_error("date_of_submission", "Date is after today")

    status_raw = data.get("status")
    if status_raw is None or (isinstance(status_raw, str) and not status_raw.strip()):
        values["status"] = None
    else:
        status_text = str(status_raw).strip()
        canon = canonical_exit_status(status_text)
        values["status"] = canon or status_text
        if canon is None:
            add_error("status", "Status is not an allowed value")

    if mark and "mark" not in errors and looks_real(mark):
        found = _find_ci(db, Customer, Customer.code, mark)
        if found:
            if not unchanged("mark"):
                values["mark"] = found.code
        elif not unchanged("mark"):
            if not confirm_new_customer:
                add_error("mark", "New mark needs confirmation")
                proposed["mark"] = mark
            else:
                insert_customer = mark

    if supplier and "supplier" not in errors and looks_real(supplier):
        found = _find_ci(db, Supplier, Supplier.name, supplier)
        if found:
            if not unchanged("supplier"):
                values["supplier"] = found.name
        elif not unchanged("supplier"):
            if not confirm_new_supplier:
                add_error("supplier", "New supplier needs confirmation")
                proposed["supplier"] = supplier
            else:
                insert_supplier = supplier

    return _finish(values, errors, warnings, proposed, insert_customer, None, insert_supplier)
