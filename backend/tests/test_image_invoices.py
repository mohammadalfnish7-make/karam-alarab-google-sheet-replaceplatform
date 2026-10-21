from pathlib import Path
from unittest.mock import patch

from tests.conftest import login


def test_image_invoices_crud_files_and_extract(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import settings

    settings.upload_dir = str(tmp_path)
    login(client)

    created = client.post("/api/image-invoices", json={"title": "Shelf scan"})
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["title"] == "Shelf scan"
    assert item["line_count"] == 0
    invoice_id = item["id"]

    listed = client.get("/api/image-invoices")
    assert listed.status_code == 200
    assert any(row["id"] == invoice_id for row in listed.json()["items"])

    line = client.post(f"/api/image-invoices/{invoice_id}/lines")
    assert line.status_code == 200, line.text
    line_id = line.json()["item"]["id"]

    put = client.put(
        f"/api/image-invoices/{invoice_id}/lines",
        json={
            "lines": [
                {
                    "id": line_id,
                    "brand_name": "Hand Brand",
                    "barcode": "",
                    "made_in": "",
                    "volume": "100ml",
                    "quantity": 12,
                }
            ]
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()["item"]
    assert body["line_count"] == 1
    assert body["lines"][0]["brand_name"] == "Hand Brand"
    assert body["lines"][0]["volume"] == "100ml"
    assert body["lines"][0]["quantity"] == 12

    image = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo" / "pallet-scale.jpg"
    assert image.is_file()
    data = image.read_bytes()
    upload = client.post(
        f"/api/image-invoices/{invoice_id}/lines/{line_id}/files",
        files=[
            ("files", ("front.jpg", data, "image/jpeg")),
            ("files", ("back.jpg", data, "image/jpeg")),
            ("labels", (None, "Front")),
            ("labels", (None, "Back")),
        ],
    )
    assert upload.status_code == 200, upload.text
    assert len(upload.json()["items"]) == 2

    files = client.get(f"/api/image-invoices/{invoice_id}/lines/{line_id}/files")
    assert files.status_code == 200
    assert len(files.json()["items"]) == 2
    file_id = files.json()["items"][0]["id"]

    viewed = client.get(f"/api/image-invoices/{invoice_id}/lines/{line_id}/files/{file_id}")
    assert viewed.status_code == 200
    assert viewed.headers["content-type"].startswith("image/")

    with patch("app.image_invoice_extract.generate_content") as mocked:
        mocked.return_value = {
            "text": (
                '{"brand_name":"AI Brand","barcode":"1234567890123","made_in":"France",'
                '"volume":"50ml","quantity":24}'
            ),
            "finish": "end_turn",
            "usage": {},
            "provider": "anthropic",
            "model": "test",
        }
        extracted = client.post(
            f"/api/image-invoices/{invoice_id}/lines/{line_id}/extract",
            json={"overwrite": False},
        )
    assert extracted.status_code == 200, extracted.text
    result = extracted.json()
    # Hand-filled brand/volume/qty kept; empty barcode/made_in filled
    assert result["item"]["brand_name"] == "Hand Brand"
    assert result["item"]["volume"] == "100ml"
    assert result["item"]["quantity"] == 12
    assert result["item"]["barcode"] == "1234567890123"
    assert result["item"]["made_in"] == "France"
    assert "barcode" in result["changed_fields"]
    assert "brand_name" not in result["changed_fields"]

    with patch("app.image_invoice_extract.generate_content") as mocked:
        mocked.return_value = {
            "text": (
                '{"brand_name":"AI Brand","barcode":"999","made_in":"Italy",'
                '"volume":"75ml","quantity":6}'
            ),
            "finish": "end_turn",
            "usage": {},
            "provider": "anthropic",
            "model": "test",
        }
        overwritten = client.post(
            f"/api/image-invoices/{invoice_id}/lines/{line_id}/extract",
            json={"overwrite": True},
        )
    assert overwritten.status_code == 200, overwritten.text
    over = overwritten.json()["item"]
    assert over["brand_name"] == "AI Brand"
    assert over["volume"] == "75ml"
    assert over["quantity"] == 6
    assert over["made_in"] == "Italy"

    removed = client.delete(f"/api/image-invoices/{invoice_id}/lines/{line_id}/files/{file_id}")
    assert removed.status_code == 200
    assert removed.json()["item"]["deleted_at"]

    deleted = client.delete(f"/api/image-invoices/{invoice_id}")
    assert deleted.status_code == 200
    assert deleted.json()["item"]["deleted_at"]

    # Soft-deleted: hidden from default list; admin can still open by id
    listed_after = client.get("/api/image-invoices")
    assert listed_after.status_code == 200
    assert all(row["id"] != invoice_id for row in listed_after.json()["items"])
    still = client.get(f"/api/image-invoices/{invoice_id}")
    assert still.status_code == 200
    assert still.json()["item"]["deleted_at"]


def test_image_invoice_export_excel_with_custom_filename(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import settings

    settings.upload_dir = str(tmp_path)
    login(client)

    created = client.post("/api/image-invoices", json={"title": "Shelf A"})
    invoice_id = created.json()["item"]["id"]
    line = client.post(f"/api/image-invoices/{invoice_id}/lines")
    line_id = line.json()["item"]["id"]
    client.put(
        f"/api/image-invoices/{invoice_id}/lines",
        json={
            "lines": [
                {
                    "id": line_id,
                    "brand_name": "Gold",
                    "barcode": "111",
                    "made_in": "France",
                    "volume": "65ml",
                    "quantity": 96,
                }
            ]
        },
    )

    empty = client.post("/api/image-invoices", json={"title": "Empty"})
    empty_id = empty.json()["item"]["id"]
    no_lines = client.post(f"/api/image-invoices/{empty_id}/export", json={"filename": "empty"})
    assert no_lines.status_code == 422

    exported = client.post(
        f"/api/image-invoices/{invoice_id}/export",
        json={"filename": "my custom invoice"},
    )
    assert exported.status_code == 200, exported.text
    assert "spreadsheetml" in exported.headers["content-type"]
    assert "my%20custom%20invoice.xlsx" in exported.headers["content-disposition"]
    assert exported.content[:2] == b"PK"

    via_get = client.get(f"/api/image-invoices/{invoice_id}/export?filename=via-get")
    assert via_get.status_code == 200
    assert "via-get.xlsx" in via_get.headers["content-disposition"]


def test_image_invoice_extract_requires_photos(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import settings

    settings.upload_dir = str(tmp_path)
    login(client)

    created = client.post("/api/image-invoices", json={})
    invoice_id = created.json()["item"]["id"]
    line = client.post(f"/api/image-invoices/{invoice_id}/lines")
    line_id = line.json()["item"]["id"]

    missing = client.post(f"/api/image-invoices/{invoice_id}/lines/{line_id}/extract")
    assert missing.status_code == 422
