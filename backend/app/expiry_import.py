"""Import Document expiry.xlsx into document_expiries (full replace).

Sheet text dates are day/month/year (e.g. 18/12/2026). Some cells were typed
the same way into Excel date cells formatted mm-dd-yy, so Excel stored month
and day swapped. Those are corrected on import.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import openpyxl
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import DocumentExpiry
from app.validation import parse_dmy


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = str(value).strip()
    return text or None


def _int(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return None


def _us_month_first_format(number_format: str | None) -> bool:
    """True when Excel format puts month before day (mm-dd-yy, m/d/yyyy, …)."""
    fmt = (number_format or "").strip().lower().replace("\\", "")
    if not fmt or fmt == "general":
        return False
    # Strip locale / color prefixes like [$-409]
    fmt = re.sub(r"\[[^\]]*]", "", fmt)
    return bool(re.match(r"^m{1,2}[-/.]", fmt))


def _swap_day_month(value: date) -> date | None:
    if value.day > 12:
        return None
    try:
        return date(value.year, value.day, value.month)
    except ValueError:
        return None


def expiry_cell_date(value, number_format: str | None = None) -> date | None:
    """Read one expiry cell as a calendar date (always day/month/year intent)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        if _us_month_first_format(number_format):
            swapped = _swap_day_month(value)
            if swapped is not None:
                return swapped
        return value
    return parse_dmy(str(value))


def _cell_date(cell) -> date | None:
    return expiry_cell_date(cell.value, cell.number_format)


def import_document_expiry(db: Session, path: Path) -> dict:
    if not path.is_file():
        return {"skipped": True, "reason": "missing", "path": str(path)}

    # Keep number formats so mm-dd-yy cells can be un-swapped to DMY.
    wb = openpyxl.load_workbook(path, data_only=False)
    now = datetime.now(timezone.utc)
    rows: list[DocumentExpiry] = []

    company = wb["Company docs"]
    for excel_row in company.iter_rows(min_row=4, max_row=company.max_row):
        # B=sl, C=name, D=no, E=company, F=expiry
        if len(excel_row) < 6:
            continue
        name = _text(excel_row[2].value)
        if not name:
            continue
        rows.append(
            DocumentExpiry(
                category="company",
                sl_no=_int(excel_row[1].value),
                title=name,
                document_type=name,
                document_no=_text(excel_row[3].value),
                company_name=_text(excel_row[4].value),
                holder_name=None,
                plate_no=None,
                expiry_date=_cell_date(excel_row[5]),
                created_at=now,
                updated_at=None,
            )
        )

    employees = wb["Employee's docs"]
    for excel_row in employees.iter_rows(min_row=4, max_row=employees.max_row):
        # B=sl, C=employee, D=document, E=company, F=doc no, G=expiry
        if len(excel_row) < 7:
            continue
        employee = _text(excel_row[2].value)
        doc = _text(excel_row[3].value)
        if not employee and not doc:
            continue
        rows.append(
            DocumentExpiry(
                category="employee",
                sl_no=_int(excel_row[1].value),
                title=employee or doc or "Employee document",
                document_type=doc,
                document_no=_text(excel_row[5].value),
                company_name=_text(excel_row[4].value),
                holder_name=employee,
                plate_no=None,
                expiry_date=_cell_date(excel_row[6]),
                created_at=now,
                updated_at=None,
            )
        )

    vehicles = wb["Vehicles"]
    for excel_row in vehicles.iter_rows(min_row=5, max_row=vehicles.max_row):
        # B=sl, C=description, D=document, E=plate, F=doc no, G=expiry
        if len(excel_row) < 7:
            continue
        description = _text(excel_row[2].value)
        if not description:
            continue
        rows.append(
            DocumentExpiry(
                category="vehicle",
                sl_no=_int(excel_row[1].value),
                title=description,
                document_type=_text(excel_row[3].value),
                document_no=_text(excel_row[5].value),
                company_name=None,
                holder_name=description,
                plate_no=_text(excel_row[4].value),
                expiry_date=_cell_date(excel_row[6]),
                created_at=now,
                updated_at=None,
            )
        )

    db.execute(delete(DocumentExpiry))
    for row in rows:
        db.add(row)
    db.commit()
    return {
        "skipped": False,
        "filename": path.name,
        "total": len(rows),
        "company": sum(1 for row in rows if row.category == "company"),
        "employee": sum(1 for row in rows if row.category == "employee"),
        "vehicle": sum(1 for row in rows if row.category == "vehicle"),
    }
