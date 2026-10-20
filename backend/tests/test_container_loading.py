from pathlib import Path
from unittest.mock import patch

from tests.conftest import login

REPO = Path(__file__).resolve().parents[2]
SAMPLE_PLAN = REPO / "continer loading imges " / "Container Load DR1249.xlsx"
DEMO_IMAGE = REPO / "frontend" / "public" / "demo" / "pallet-scale.jpg"


def test_container_loading_crud_and_images(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import settings

    settings.upload_dir = str(tmp_path)

    login(client)

    next_mark = client.get("/api/container-loading/next-mark")
    assert next_mark.status_code == 200
    assert next_mark.json()["mark"] == "CL1"

    created = client.post("/api/container-loading", json={"container_no": "MSCU123"})
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["mark"] == "CL1"
    assert item["container_no"] == "MSCU123"
    item_id = item["id"]

    second = client.post("/api/container-loading", json={})
    assert second.status_code == 200
    assert second.json()["item"]["mark"] == "CL2"

    patched = client.patch(
        f"/api/container-loading/{item_id}",
        json={"mark": "DR1243 load", "container_no": "MSCU999"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["item"]["mark"] == "DR1243 load"
    assert patched.json()["item"]["container_no"] == "MSCU999"

    listed = client.get("/api/container-loading?q=MSCU999")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    assert DEMO_IMAGE.is_file()
    upload = client.post(
        f"/api/container-loading/{item_id}/files",
        files=[
            ("files", ("loading.jpg", DEMO_IMAGE.read_bytes(), "image/jpeg")),
            ("labels", (None, "Loading 1")),
        ],
    )
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["items"][0]["id"]
    assert upload.json()["items"][0]["kind"] == "loading"

    audits = client.get("/api/audit", params={"entity_type": "container_loading", "entity_id": str(item_id)})
    assert audits.status_code == 200
    upload_audit = next(item for item in audits.json()["items"] if item["action"] == "upload_photo")
    change = upload_audit["changed_fields"][0]
    assert change["field"] == "photos"
    assert "loading.jpg" in change["new"]

    viewed = client.get(f"/api/container-loading/{item_id}/files/{file_id}")
    assert viewed.status_code == 200

    extract_payload = {
        "pallets": [
            {
                "side": "left",
                "marks": [{"name": "PARIS CORNER 1", "mix": 1, "cartons": 26, "notes": None}],
            },
            {
                "side": "right",
                "marks": [
                    {"name": "WADI SIJI 2", "mix": 2, "cartons": 49, "notes": None},
                    {"name": "OTHER MARK", "mix": 2, "cartons": 8, "notes": "same pallet"},
                ],
            },
        ],
        "issues": [],
        "notes": None,
        "readable": True,
    }
    with patch("app.container_loading_extract.generate_content") as mocked:
        mocked.return_value = {
            "text": __import__("json").dumps(extract_payload),
            "finish": "end_turn",
            "usage": {},
            "provider": "test",
            "model": "test",
        }
        extracted = client.post(f"/api/container-loading/{item_id}/files/{file_id}/extract")
    assert extracted.status_code == 200, extracted.text
    body = extracted.json()
    assert len(body["extracted"]["pallets"]) == 2
    assert len(body["extracted"]["pallets"][1]["marks"]) == 2

    edited = {
        "pallets": [
            {"side": "left", "marks": [{"name": "PARIS CORNER 1", "mix": 1, "cartons": 26}]},
            {"side": "right", "marks": [{"name": "WADI SIJI 2", "mix": 2, "cartons": 50}]},
        ],
        "issues": [],
        "notes": "edited",
        "readable": True,
    }
    patched_extract = client.patch(
        f"/api/container-loading/{item_id}/files/{file_id}/extracted",
        json=edited,
    )
    assert patched_extract.status_code == 200, patched_extract.text
    assert patched_extract.json()["extracted"]["notes"] == "edited"
    assert patched_extract.json()["extracted"]["pallets"][1]["marks"][0]["cartons"] == 50

    assert SAMPLE_PLAN.is_file()
    plan_upload = client.post(
        f"/api/container-loading/{item_id}/plan",
        files={"file": ("Container Load DR1249.xlsx", SAMPLE_PLAN.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert plan_upload.status_code == 200, plan_upload.text
    plan_item = plan_upload.json()["item"]
    assert plan_item["plan_line_count"] >= 40
    assert plan_item["plan"]["container_number"] == "25279"
    # container_no was already set; plan fills only when empty (no Cont Tracker link)
    assert plan_item["container_no"] == "MSCU999"
    assert plan_item.get("container_row_id") is None

    check_payload = {
        "ok": False,
        "matched": ["PARIS CORNER 1", "WADI SIJI 2"],
        "missing_from_photos": ["NATIONAL TRADERS 5"],
        "extra_in_photos": [],
        "mismatches": [],
        "notes": "incomplete photos",
    }
    with patch("app.container_loading_extract.generate_content") as mocked:
        mocked.return_value = {
            "text": __import__("json").dumps(check_payload),
            "finish": "end_turn",
            "usage": {},
            "provider": "test",
            "model": "test",
        }
        summarized = client.post(f"/api/container-loading/{item_id}/summarize")
    assert summarized.status_code == 200, summarized.text
    assert summarized.json()["check"]["missing_from_photos"]
    assert summarized.json()["item"]["check"]["ok"] is False
    assert summarized.json()["summary"]["mark_count"] >= 2

    deleted_file = client.delete(f"/api/container-loading/{item_id}/files/{file_id}")
    assert deleted_file.status_code == 200
    assert deleted_file.json()["item"]["deleted_at"] is not None

    restored_file = client.post(f"/api/container-loading/{item_id}/files/{file_id}/restore")
    assert restored_file.status_code == 200
    assert restored_file.json()["item"]["deleted_at"] is None

    deleted = client.delete(f"/api/container-loading/{item_id}")
    assert deleted.status_code == 200
    gone = client.get("/api/container-loading?q=MSCU999")
    assert all(row["id"] != item_id for row in gone.json()["items"])

    reused = client.post(
        "/api/container-loading",
        json={"mark": "DR1243 load", "container_no": "MSCU777"},
    )
    assert reused.status_code == 200, reused.text
    assert reused.json()["item"]["mark"] == "DR1243 load"
    reused_id = reused.json()["item"]["id"]

    blocked = client.post(f"/api/container-loading/{item_id}/restore")
    assert blocked.status_code == 422

    client.delete(f"/api/container-loading/{reused_id}")
    restored = client.post(f"/api/container-loading/{item_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["item"]["deleted_at"] is None
