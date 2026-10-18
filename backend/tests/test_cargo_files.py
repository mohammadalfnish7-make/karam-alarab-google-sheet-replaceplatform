from pathlib import Path

from tests.conftest import login, sea_payload


def test_upload_list_view_and_download_cargo_files(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import settings

    settings.upload_dir = str(tmp_path)

    login(client)
    created = client.post("/api/sea", json=sea_payload())
    assert created.status_code == 200, created.text
    item_id = created.json()["item"]["id"]

    image = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo" / "pallet-scale.jpg"
    pdf = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo" / "sample-delivery-note.pdf"
    assert image.is_file()
    assert pdf.is_file()

    upload = client.post(
        f"/api/sea/{item_id}/files",
        files=[
            ("files", ("note.pdf", pdf.read_bytes(), "application/pdf")),
            ("files", ("scale.jpg", image.read_bytes(), "image/jpeg")),
            ("kinds", (None, "note")),
            ("kinds", (None, "scale")),
            ("labels", (None, "Note 1")),
            ("labels", (None, "Scale 1")),
            ("extracted", (None, '{"cartons": 10}')),
            ("extracted", (None, '{"scale_weight_kg": 12.5}')),
        ],
    )
    assert upload.status_code == 200, upload.text
    items = upload.json()["items"]
    assert len(items) == 2
    assert items[0]["kind"] == "note"
    assert items[0]["is_pdf"] is True
    assert items[1]["kind"] == "scale"
    assert items[1]["is_image"] is True

    listed = client.get(f"/api/sea/{item_id}/files")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["extracted"]["cartons"] == 10

    file_id = items[1]["id"]
    viewed = client.get(f"/api/sea/{item_id}/files/{file_id}")
    assert viewed.status_code == 200
    assert viewed.headers["content-type"].startswith("image/")
    assert "inline" in viewed.headers.get("content-disposition", "").lower()

    downloaded = client.get(f"/api/sea/{item_id}/files/{file_id}/download")
    assert downloaded.status_code == 200
    assert "attachment" in downloaded.headers.get("content-disposition", "").lower()

    sheet = client.get("/api/sea")
    assert sheet.status_code == 200
    row = next(item for item in sheet.json()["items"] if item["id"] == item_id)
    assert row["file_count"] == 2
