from pathlib import Path

from tests.conftest import login


def test_air_shipment_pictures_crud_and_multi_photos(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import settings

    settings.upload_dir = str(tmp_path)
    login(client)

    next_number = client.get("/api/air-shipment-pictures/next-number")
    assert next_number.status_code == 200
    assert next_number.json()["number"] == "AR001"

    created = client.post(
        "/api/air-shipment-pictures",
        json={"number": "AR087", "cartons": 85},
    )
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["number"] == "AR087"
    assert item["cartons"] == 85
    assert item["date"]
    item_id = item["id"]

    next_after = client.get("/api/air-shipment-pictures/next-number")
    assert next_after.status_code == 200
    assert next_after.json()["number"] == "AR088"

    patched = client.patch(f"/api/air-shipment-pictures/{item_id}", json={"cartons": 90})
    assert patched.status_code == 200
    assert patched.json()["item"]["cartons"] == 90

    image = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo" / "pallet-scale.jpg"
    assert image.is_file()
    data = image.read_bytes()
    upload = client.post(
        f"/api/air-shipment-pictures/{item_id}/files",
        files=[
            ("files", ("p1.jpg", data, "image/jpeg")),
            ("files", ("p2.jpg", data, "image/jpeg")),
        ],
    )
    assert upload.status_code == 200, upload.text
    assert len(upload.json()["items"]) == 2
    assert upload.json()["items"][0]["kind"] == "photo"

    listed = client.get(f"/api/air-shipment-pictures/{item_id}/files")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2

    file_id = listed.json()["items"][0]["id"]
    viewed = client.get(f"/api/air-shipment-pictures/{item_id}/files/{file_id}")
    assert viewed.status_code == 200

    deleted = client.delete(f"/api/air-shipment-pictures/{item_id}")
    assert deleted.status_code == 200
    gone = client.get("/api/air-shipment-pictures?q=AR087")
    assert all(row["id"] != item_id for row in gone.json()["items"])

    restored = client.post(f"/api/air-shipment-pictures/{item_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["item"]["deleted_at"] is None
