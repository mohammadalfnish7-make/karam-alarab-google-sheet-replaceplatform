"""Build Excel workbook from an image invoice's product lines."""

from __future__ import annotations

import io
import re
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from app.errors import AppError
from app.image_invoices import _lines_for
from app.models import ImageInvoice
from app.present import num

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_HEADERS = ("No", "Brand name", "Barcode", "Made in", "Volume", "Quantity")


def sanitize_filename(raw: str | None, *, fallback: str) -> str:
    base = (raw or "").strip() or fallback
    base = _UNSAFE.sub("-", base).strip(" .")
    if not base:
        base = fallback
    if not base.lower().endswith(".xlsx"):
        base = f"{base}.xlsx"
    return base[:180]


def build_workbook(db: Session, invoice: ImageInvoice) -> bytes:
    lines = _lines_for(db, invoice.id)
    if not lines:
        raise AppError(422, {"message": "Add at least one product row before export"})

    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice"
    ws.append(list(_HEADERS))
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for index, line in enumerate(lines, start=1):
        ws.append(
            [
                index,
                line.brand_name or "",
                line.barcode or "",
                line.made_in or "",
                line.volume or "",
                num(line.quantity),
            ]
        )

    for column in ws.columns:
        letter = column[0].column_letter
        width = max(len(str(cell.value or "")) for cell in column)
        ws.column_dimensions[letter].width = min(max(width + 2, 10), 40)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def export_payload(
    db: Session,
    invoice: ImageInvoice,
    *,
    filename: str | None,
) -> tuple[bytes, str]:
    fallback = invoice.title or f"image-invoice-{invoice.id}"
    name = sanitize_filename(filename, fallback=fallback)
    content = build_workbook(db, invoice)
    return content, name


def export_meta(filename: str) -> dict[str, Any]:
    return {"filename": filename}
