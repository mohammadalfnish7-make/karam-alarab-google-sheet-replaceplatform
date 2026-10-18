from sqlalchemy import select

from app.database import SessionLocal
from app.models import RequestLog
from tests.conftest import login


def test_api_requests_are_logged(client):
    login(client)
    ping = client.get("/api/lookups/enums")
    assert ping.status_code == 200

    db = SessionLocal()
    try:
        rows = db.scalars(select(RequestLog).order_by(RequestLog.id.desc())).all()
    finally:
        db.close()
    match = next((row for row in rows if row.path == "/api/lookups/enums"), None)
    assert match is not None
    assert match.method == "GET"
    assert match.status_code == 200
    assert match.duration_ms >= 0
    assert match.actor_user_id is not None

    listed = client.get("/api/request-logs")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    assert any(item["path"] == "/api/lookups/enums" for item in body["items"])


def test_health_is_not_logged(client):
    before = SessionLocal()
    try:
        count_before = len(before.scalars(select(RequestLog)).all())
    finally:
        before.close()
    assert client.get("/api/health").status_code == 200
    after = SessionLocal()
    try:
        count_after = len(after.scalars(select(RequestLog)).all())
    finally:
        after.close()
    assert count_after == count_before
