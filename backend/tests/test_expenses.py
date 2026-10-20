from pathlib import Path
from unittest.mock import patch

from tests.conftest import login


def test_expenses_crud_budget_and_multi_photos(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import settings

    settings.upload_dir = str(tmp_path)
    login(client)

    next_mark = client.get("/api/expenses/next-mark")
    assert next_mark.status_code == 200
    assert next_mark.json()["mark"] == "EX1"

    created = client.post("/api/expenses", json={"amount": 100, "currency": "AED", "notes": "locks"})
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["mark"] == "EX1"
    assert item["amount"] == 100
    assert item["currency"] == "AED"
    assert item["date"]
    assert created.json()["budget"]["spent"] == 100
    item_id = item["id"]

    over = client.post("/api/expenses", json={"amount": 1950, "currency": "AED"})
    assert over.status_code == 422

    ok = client.post("/api/expenses", json={"amount": 50, "currency": "USD", "notes": "non-AED"})
    assert ok.status_code == 200

    image = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo" / "pallet-scale.jpg"
    assert image.is_file()
    data = image.read_bytes()
    upload = client.post(
        f"/api/expenses/{item_id}/files",
        files=[
            ("files", ("r1.jpg", data, "image/jpeg")),
            ("files", ("r2.jpg", data, "image/jpeg")),
            ("labels", (None, "Receipt 1")),
            ("labels", (None, "Receipt 2")),
        ],
    )
    assert upload.status_code == 200, upload.text
    assert len(upload.json()["items"]) == 2

    listed = client.get(f"/api/expenses/{item_id}/files")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2

    with patch("app.expense_summarize.generate_content") as mocked:
        mocked.return_value = {
            "text": (
                '{"vendor":"Test Shop","date":"2026-10-18","amount":21,"currency":"AED",'
                '"receipt_no":"45212","category":"Hardware","payment_method":"Cash",'
                '"vat_amount":1,"subtotal":20,"total":21,"line_items":[{"description":"lock","qty":1,"amount":21}],'
                '"notes":"Paid lock","raw_text":null}'
            ),
            "finish": "end_turn",
            "usage": {},
            "provider": "anthropic",
            "model": "test",
        }
        # amount already set — should not overwrite
        summarized = client.post(f"/api/expenses/{item_id}/summarize")
    assert summarized.status_code == 200, summarized.text
    body = summarized.json()
    assert body["summary"]["vendor"] == "Test Shop"
    assert body["item"]["summary"]["receipt_no"] == "45212"
    assert body["item"]["amount"] == 100

    empty = client.post("/api/expenses", json={"notes": "fill me"})
    assert empty.status_code == 200
    empty_id = empty.json()["item"]["id"]
    client.post(
        f"/api/expenses/{empty_id}/files",
        files=[("files", ("r.jpg", data, "image/jpeg"))],
    )
    with patch("app.expense_summarize.generate_content") as mocked:
        mocked.return_value = {
            "text": '{"vendor":"X","amount":25,"currency":"AED","date":"2026-10-01","line_items":[],"notes":"n"}',
            "finish": "end_turn",
            "usage": {},
            "provider": "anthropic",
            "model": "test",
        }
        filled = client.post(f"/api/expenses/{empty_id}/summarize")
    assert filled.status_code == 200, filled.text
    assert filled.json()["item"]["amount"] == 25
    assert filled.json()["item"]["currency"] == "AED"

    deleted = client.delete(f"/api/expenses/{item_id}")
    assert deleted.status_code == 200
    budget = client.get("/api/expenses/budget")
    assert budget.status_code == 200
    assert budget.json()["spent"] == 25
