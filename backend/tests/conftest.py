import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "change-me"
os.environ["EXCEL_IMPORT_PATH"] = ""
os.environ["TESTING"] = "1"
os.environ["GEMINI_API_KEY"] = ""
os.environ["UPLOAD_DIR"] = "/tmp/karam-test-uploads"

from fastapi.testclient import TestClient
from sqlalchemy import delete
import pytest

from app.bootstrap import seed_admin
from app.database import Base, SessionLocal
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_db(client):
    client.cookies.clear()
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
        seed_admin(db)
    finally:
        db.close()
    yield


def login(client, email="admin@example.com", password="change-me"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    assert "httponly" in response.headers["set-cookie"].lower()
    return response.json()


def sea_payload(**overrides):
    data = {
        "company_name": "Acme",
        "confirm_new_company": True,
        "cartons": 1,
        "gross_weight_kg": 10,
        "net_weight_kg": 4,
        "system_code": "DL1001",
        "shipment_number": "D1001",
        "shipping_route": "IRAN",
        "stage": "STAGE 1",
        "date_received": "2026-10-01",
    }
    data.update(overrides)
    return data
