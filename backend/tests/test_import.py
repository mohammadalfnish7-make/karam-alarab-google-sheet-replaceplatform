from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from app.database import SessionLocal
from app.importer import import_workbook
from app.models import Customer, ExitRecord, SeaCargo

WORKBOOK = Path(__file__).resolve().parents[2] / "excel sheet" / "WM _NEW  Load Plan.xlsx"


def test_import_real_workbook(client):
    assert client.get("/api/health").status_code == 200
    assert WORKBOOK.is_file()
    db = SessionLocal()
    try:
        result = import_workbook(db, WORKBOOK)
        assert result["skipped"] is False
        assert result["sea"] == 1859
        assert result["air"] == 549
        assert result["exit"] == 465
        row = db.scalar(select(SeaCargo).where(SeaCargo.system_code == "DL3027"))
        assert row is not None
        assert row.company_name == "JUMANAH"
        assert row.customer_code == "4001"
        assert row.cartons == 118
        assert row.stage == "📦 WH"
        assert float(row.gross_weight_kg) == 376.5
        assert row.gross_is_no_pallet is False
        assert row.date_received == date(2026, 10, 10)
        assert row.needs_review is False
        assert db.scalar(select(func.count()).select_from(SeaCargo).where(SeaCargo.shipping_route == "TURKY")) == 0
        transit = db.scalar(select(SeaCargo).where(SeaCargo.shipping_route == "IRAN TRANSIT"))
        assert transit is not None
        assert transit.needs_review is True
        assert db.scalar(select(func.count()).select_from(ExitRecord).where(ExitRecord.status == "PENDING")) == 0
        assert db.scalar(select(Customer).where(Customer.code == "4455")) is not None
        codes = db.scalars(select(Customer.code)).all()
        assert codes
        assert all(any(ch.isalnum() for ch in code) for code in codes)
        again = import_workbook(db, WORKBOOK)
        assert again["skipped"] is True
        assert db.scalar(select(func.count()).select_from(SeaCargo)) == 1859
    finally:
        db.close()
