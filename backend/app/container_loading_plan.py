"""Parse standalone container loading plan Excel (LOADING LIST + COMMODITY)."""

from __future__ import annotations

import io
import re
from typing import Any

import openpyxl

from app.errors import AppError

_CONTAINER_RE = re.compile(r"CONTAINER\s*NUMBER\s*:\s*(.+)", re.IGNORECASE)


def _cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value


def _intish(value: Any) -> int | None:
    value = _cell(value)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else int(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else int(number)


def _floatish(value: Any) -> float | int | None:
    value = _cell(value)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if isinstance(value, float) and value.is_integer() else value
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _text(value: Any) -> str | None:
    value = _cell(value)
    if value is None:
        return None
    return str(value).strip() or None


def parse_loading_plan(content: bytes, *, filename: str | None = None) -> dict[str, Any]:
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001
        raise AppError(422, {"message": f"Could not read Excel: {exc}"}) from exc

    sheet_names = {name.strip().upper(): name for name in wb.sheetnames}
    list_name = sheet_names.get("LOADING LIST")
    if not list_name:
        raise AppError(422, {"message": "Workbook must include a LOADING LIST sheet"})

    lines: list[dict[str, Any]] = []
    ws = wb[list_name]
    for index, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if index == 1:
            continue
        cells = list(row) if row else []
        while len(cells) < 10:
            cells.append(None)
        no_raw = _text(cells[0])
        name = _text(cells[4])
        cartons = _intish(cells[5])
        if no_raw and no_raw.lower().startswith("total"):
            break
        if not name and cartons is None:
            continue
        if no_raw and not no_raw.replace(".", "", 1).isdigit() and not name:
            continue
        lines.append(
            {
                "no": _intish(cells[0]),
                "customer_code": _text(cells[1]),
                "cust_name": _text(cells[2]),
                "mix": _intish(cells[3]),
                "name": name,
                "cartons": cartons,
                "weight": _floatish(cells[6]),
                "pw": _floatish(cells[7]),
                "total_weight": _floatish(cells[9]),
            }
        )

    container_number: str | None = None
    commodities: list[dict[str, Any]] = []
    commodity_name = sheet_names.get("COMMODITY")
    if commodity_name:
        cws = wb[commodity_name]
        for index, row in enumerate(cws.iter_rows(values_only=True), start=1):
            cells = list(row) if row else []
            if index == 1:
                first = _text(cells[0] if cells else None)
                if first:
                    match = _CONTAINER_RE.search(first)
                    if match:
                        container_number = match.group(1).strip() or None
                continue
            if index == 2:
                continue
            category = _text(cells[2] if len(cells) > 2 else None)
            qty = _intish(cells[4] if len(cells) > 4 else None)
            weight = _floatish(cells[5] if len(cells) > 5 else None)
            if not category and qty is None and weight is None:
                continue
            commodities.append(
                {
                    "no": _intish(cells[0] if cells else None),
                    "hs_code": _text(cells[1] if len(cells) > 1 else None),
                    "category": category,
                    "coo": _text(cells[3] if len(cells) > 3 else None),
                    "qty": qty,
                    "weight": weight,
                }
            )

    if not lines:
        raise AppError(422, {"message": "LOADING LIST has no usable rows"})

    return {
        "filename": filename,
        "container_number": container_number,
        "lines": lines,
        "commodities": commodities,
        "line_count": len(lines),
    }
