from datetime import datetime, timezone

from app.database import SessionLocal
from app.importer import repair_dates_after_today, repair_invoice_numbers
from app.models import ExitRecord
from app.validation import split_invoices
from tests.conftest import login


def test_sheet_cells_split_into_each_invoice():
    assert split_invoices("2026/00104-00105-00106-00107-00108") == [
        "2026/00104",
        "2026/00105",
        "2026/00106",
        "2026/00107",
        "2026/00108",
    ]
    assert split_invoices("3746-3749-3755") == ["3746", "3749", "3755"]
    assert split_invoices("SLI002070-SLI002123") == ["SLI002070", "SLI002123"]
    assert split_invoices("80306278 / 80305550") == ["80306278", "80305550"]
    assert split_invoices("19153-19154-\n 19155") == ["19153", "19154", "19155"]
    assert split_invoices("SMELL262014528-JIZAN26901831-\n EMAROSE GROP012-26") == [
        "SMELL262014528",
        "JIZAN26901831",
        "EMAROSE GROP012-26",
    ]
    assert split_invoices("399-484-169A") == ["399", "484", "169A"]
    assert split_invoices("SL-22891-26") == ["SL-22891-26"]
    assert split_invoices("013-26") == ["013-26"]
    assert split_invoices("24/68414") == ["24/68414"]
    assert split_invoices("CR26-27/316/317") == ["CR26-27/316/317"]
    assert split_invoices("263008986") == ["263008986"]
    assert split_invoices("016-26/ 017-26") == ["016-26", "017-26"]
    assert split_invoices("17782/17783") == ["17782", "17783"]
    assert split_invoices("26902050/SO2614203") == ["26902050", "SO2614203"]
    assert split_invoices("DV04/79674") == ["DV04/79674"]
    assert split_invoices("2026/00028, 2026/00030, 2026/00031") == ["2026/00028", "2026/00030", "2026/00031"]


def test_exit_save_stores_every_invoice(client):
    login(client)
    created = client.post(
        "/api/exit",
        json={
            "supplier": "Karam al oud",
            "confirm_new_supplier": True,
            "invoice_no": "2026/00104-00105-00106",
            "status": "Pending",
        },
    )
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["invoice_numbers"] == ["2026/00104", "2026/00105", "2026/00106"]
    assert item["invoice_no"] == "2026/00104, 2026/00105, 2026/00106"
    found = client.get("/api/exit", params={"q": "00105"})
    assert found.status_code == 200, found.text
    assert found.json()["total"] == 1

    single = client.post(
        "/api/exit",
        json={
            "supplier": "AL SADAD",
            "confirm_new_supplier": True,
            "invoice_numbers": ["SL-22891-26"],
            "status": "Pending",
        },
    )
    assert single.status_code == 200, single.text
    assert single.json()["item"]["invoice_numbers"] == ["SL-22891-26"]


def test_repair_splits_existing_invoice_cells(client):
    db = SessionLocal()
    try:
        db.add(
            ExitRecord(
                legacy=True,
                needs_review=False,
                issues=[],
                no=50,
                supplier="EMAROS",
                invoice_no="2026/00028-00030-00031",
                invoice_numbers=None,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        assert repair_invoice_numbers(db)["invoices_split"] == 1
        row = db.query(ExitRecord).filter(ExitRecord.no == 50).one()
        assert row.invoice_numbers == ["2026/00028", "2026/00030", "2026/00031"]
        assert repair_invoice_numbers(db)["invoices_split"] == 0
    finally:
        db.close()


def test_repair_brings_exit_dates_back(client):
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.add(
            ExitRecord(
                legacy=True,
                needs_review=True,
                issues=[{"field": "date_of_submission", "message": "Date is after today", "raw": "2026-11-07"}],
                no=60,
                supplier="FRENCH FRAGRANCE",
                date_of_submission=datetime(2026, 11, 7).date(),
                created_at=now,
            )
        )
        db.add(
            ExitRecord(
                legacy=True,
                needs_review=True,
                issues=[{"field": "date_of_submission", "message": "Invalid date", "raw": "1107/2026"}],
                no=61,
                supplier="CANNES",
                date_of_submission=None,
                created_at=now,
            )
        )
        db.commit()
        repaired = repair_dates_after_today(db)
        assert repaired["exit_corrected"] == 2
        november = db.query(ExitRecord).filter(ExitRecord.no == 60).one()
        compact = db.query(ExitRecord).filter(ExitRecord.no == 61).one()
        assert november.date_of_submission.isoformat() == "2026-07-11"
        assert november.needs_review is False
        assert compact.date_of_submission.isoformat() == "2026-07-11"
        assert compact.issues == []
    finally:
        db.close()
