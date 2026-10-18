from datetime import date, datetime
from pathlib import Path

from app.database import SessionLocal
from app.expiry import list_expiry, urgency
from app.expiry_import import expiry_cell_date, import_document_expiry
from tests.conftest import login


def test_urgency_buckets():
    today = date(2026, 10, 17)
    assert urgency(date(2026, 10, 1), today=today)["status"] == "expired"
    assert urgency(date(2026, 10, 17), today=today)["status"] == "urgent"
    assert urgency(date(2026, 11, 1), today=today)["status"] == "urgent"
    assert urgency(date(2026, 12, 1), today=today)["status"] == "soon"
    assert urgency(date(2027, 6, 1), today=today)["status"] == "ok"


def test_us_excel_dates_swap_back_to_dmy():
    # Sheet intent is 07/12/2026 (7 Dec); Excel mm-dd-yy stored July 12.
    assert expiry_cell_date(datetime(2026, 7, 12), "mm-dd-yy") == date(2026, 12, 7)
    assert expiry_cell_date(datetime(2027, 2, 10), "mm-dd-yy") == date(2027, 10, 2)
    # Text DD/MM stays as typed.
    assert expiry_cell_date("18/12/2026", "General") == date(2026, 12, 18)
    # Real July 12 kept when format is not month-first.
    assert expiry_cell_date(datetime(2026, 7, 12), "yyyy-mm-dd") == date(2026, 7, 12)


def test_import_and_list_expiry(client):
    source = Path(__file__).resolve().parents[2] / "excel sheet" / "Document expiry.xlsx"
    assert source.is_file()
    db = SessionLocal()
    try:
        result = import_document_expiry(db, source)
    finally:
        db.close()
    assert result["skipped"] is False
    assert result["total"] == 20
    assert result["company"] == 8
    assert result["employee"] == 7
    assert result["vehicle"] == 5

    login(client)
    response = client.get("/api/expiry")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["total"] == 20
    assert body["summary"]["expired"] >= 1

    company = client.get("/api/expiry", params={"category": "company"})
    assert company.status_code == 200
    assert all(item["category"] == "company" for item in company.json()["items"])

    expired = client.get("/api/expiry", params={"status": "expired"})
    assert expired.status_code == 200
    assert all(item["status"] == "expired" for item in expired.json()["items"])


def test_patch_expiry_date_writes_audit(client):
    from datetime import datetime, timezone

    from app.models import DocumentExpiry

    db = SessionLocal()
    try:
        row = DocumentExpiry(
            category="company",
            sl_no=1,
            title="Trade license",
            document_type="Trade license",
            document_no="1279269",
            company_name="Karm al oud",
            holder_name=None,
            plate_no=None,
            expiry_date=date(2026, 12, 18),
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        item_id = row.id
    finally:
        db.close()

    login(client)
    response = client.patch(f"/api/expiry/{item_id}", json={"expiry_date": "20/12/2026"})
    assert response.status_code == 200, response.text
    assert response.json()["expiry_date"] == "2026-12-20"

    history = client.get(f"/api/expiry/{item_id}/history")
    assert history.status_code == 200
    entries = history.json()
    assert len(entries) == 1
    assert entries[0]["action"] == "update"
    assert entries[0]["entity_type"] == "document_expiry"
    assert entries[0]["changed_fields"][0]["field"] == "expiry_date"
    assert entries[0]["changed_fields"][0]["old"] == "2026-12-18"
    assert entries[0]["changed_fields"][0]["new"] == "2026-12-20"

    audit = client.get("/api/audit", params={"entity_type": "document_expiry", "entity_id": str(item_id)})
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1


def test_workbook_keeps_dmy_and_sorts_expired_first():
    db = SessionLocal()
    try:
        source = Path(__file__).resolve().parents[2] / "excel sheet" / "Document expiry.xlsx"
        import_document_expiry(db, source)
        payload = list_expiry(db, today=date(2026, 10, 17))
    finally:
        db.close()
    assert payload["items"][0]["status"] == "expired"
    by_title = {item["title"]: item for item in payload["items"]}
    # Tenancy Contact was Excel datetime(2026, 7, 12) mm-dd-yy → 7 Dec 2026
    assert by_title["Tenancy Contact"]["expiry_date"] == "2026-12-07"
    # Trade license text 18/12/2026 stays 18 Dec
    assert by_title["Trade license"]["expiry_date"] == "2026-12-18"
