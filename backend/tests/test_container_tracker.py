from pathlib import Path

from sqlalchemy import func, select

from app.container_import import import_container_tracker
from app.database import SessionLocal
from app.models import AirShipmentTrackerRow, ContainerRow, CooRow, FlightScheduleRow, ImportBatch

WORKBOOK = Path(__file__).resolve().parents[2] / "excel sheet" / "Karam Al Arab-Contanier Tracker (1).xlsx"


def _login(client, email="admin@example.com", password="change-me"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def test_import_four_sheets_and_skips_credentials(client):
    assert WORKBOOK.is_file(), f"missing {WORKBOOK}"
    db = SessionLocal()
    try:
        first = import_container_tracker(db, WORKBOOK)
        assert first["skipped"] is False
        assert first["containers"] >= 100
        assert first["air_tracker"] >= 20
        assert first["coo"] >= 50
        assert first["flight_schedule"] >= 5
        cont = db.scalar(select(func.count()).select_from(ContainerRow))
        air = db.scalar(select(func.count()).select_from(AirShipmentTrackerRow))
        coo = db.scalar(select(func.count()).select_from(CooRow))
        flight = db.scalar(select(func.count()).select_from(FlightScheduleRow))
        assert cont == first["containers"]
        assert air == first["air_tracker"]
        assert coo == first["coo"]
        assert flight == first["flight_schedule"]
        sample = db.scalar(select(ContainerRow).where(ContainerRow.inv_no.is_not(None)))
        assert sample is not None
        assert sample.container_no is not None or sample.inv_no is not None

        second = import_container_tracker(db, WORKBOOK)
        assert second["skipped"] is True
        batches = db.scalars(
            select(ImportBatch).where(ImportBatch.filename.like("container-tracker:%"))
        ).all()
        assert len(batches) == 1
    finally:
        db.close()


def test_containers_crud(client):
    _login(client)
    created = client.post(
        "/api/containers",
        json={
            "inv_no": "9999",
            "container_no": "TEST-CONT",
            "status": "In transit",
            "supplier_buyer": "Acme",
        },
    )
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["inv_no"] == "9999"
    assert item["status"] == "In transit"

    listed = client.get("/api/containers?q=9999")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    patched = client.patch(f"/api/containers/{item['id']}", json={"status": "Delivered"})
    assert patched.status_code == 200
    assert patched.json()["item"]["status"] == "Delivered"

    deleted = client.delete(f"/api/containers/{item['id']}")
    assert deleted.status_code == 200
    gone = client.get("/api/containers?q=9999")
    assert all(row["id"] != item["id"] for row in gone.json()["items"])


def test_air_tracker_and_coo_and_flight(client):
    _login(client)
    air = client.post(
        "/api/air-tracker",
        json={"ref_no": "AR999", "vendor": "AMG", "airline": "BLV", "status": "Booked"},
    )
    assert air.status_code == 200, air.text
    assert air.json()["item"]["ref_no"] == "AR999"

    coo = client.post("/api/coo", json={"inv_number": "1200", "container_no": "AB123", "kjs": "Done"})
    assert coo.status_code == 200, coo.text

    flight = client.post("/api/flight-schedule", json={"airline": "Belavia", "status": "OK"})
    assert flight.status_code == 200, flight.text

    for path in ("/api/air-tracker", "/api/coo", "/api/flight-schedule"):
        response = client.get(path)
        assert response.status_code == 200
        assert "items" in response.json()
