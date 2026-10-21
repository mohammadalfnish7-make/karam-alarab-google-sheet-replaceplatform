from pathlib import Path

from tests.conftest import login

REPO = Path(__file__).resolve().parents[2]
SAMPLE_INVOICE = REPO / "DR1249-INVOICE.xlsx"


def test_loading_invoice_create_put_upload_link(client):
    login(client)

    loading = client.post("/api/container-loading", json={"mark": "DR1249", "container_no": "25279"})
    assert loading.status_code == 200, loading.text
    loading_id = loading.json()["item"]["id"]

    created = client.post(
        "/api/loading-invoices",
        json={"ref": "DR1249", "container_loading_id": loading_id, "container_no": "25279"},
    )
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["ref"] == "DR1249"
    assert item["container_loading_id"] == loading_id
    assert item["loading_mark"] == "DR1249"
    invoice_id = item["id"]

    put = client.put(
        f"/api/loading-invoices/{invoice_id}",
        json={
            "ref": "DR1249",
            "container_loading_id": loading_id,
            "container_no": "25279",
            "lines": [
                {
                    "no": 1,
                    "mark": "5001",
                    "shop": "PARIS CORNER",
                    "description": "GOLD 65ML",
                    "pcs": 96,
                    "cartons": 10,
                    "weight": 100.5,
                },
                {
                    "no": 2,
                    "mark": "5001",
                    "shop": "PARIS CORNER",
                    "description": "SILVER 65ML",
                    "pcs": 48,
                },
            ],
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()["item"]
    assert body["line_count"] == 2
    assert body["group_count"] == 1
    assert body["total_cartons"] == 10
    assert body["total_weight"] == 100.5
    assert body["invoice"]["groups"][0]["shop"] == "PARIS CORNER"

    bad = client.put(
        f"/api/loading-invoices/{invoice_id}",
        json={"ref": "DR1249", "lines": [{"mark": "1", "description": ""}]},
    )
    assert bad.status_code == 422

    assert SAMPLE_INVOICE.is_file()
    upload = client.post(
        f"/api/loading-invoices/{invoice_id}/file",
        files={
            "file": (
                "DR1249-INVOICE.xlsx",
                SAMPLE_INVOICE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 200, upload.text
    uploaded = upload.json()["item"]
    assert uploaded["ref"] == "DR1249"
    assert uploaded["line_count"] >= 100
    assert uploaded["group_count"] >= 10
    assert uploaded["container_loading_id"] == loading_id

    loading_get = client.get(f"/api/container-loading/{loading_id}")
    assert loading_get.status_code == 200
    invoices = loading_get.json()["item"]["invoices"]
    assert any(inv["id"] == invoice_id for inv in invoices)

    unlinked = client.patch(
        f"/api/loading-invoices/{invoice_id}",
        json={"container_loading_id": None},
    )
    assert unlinked.status_code == 200
    assert unlinked.json()["item"]["container_loading_id"] is None
