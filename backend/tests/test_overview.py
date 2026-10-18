from tests.conftest import login, sea_payload


def air_payload(**overrides):
    data = {
        "company_name": "Air Co",
        "confirm_new_company": True,
        "cartons": 2,
        "gross_weight_kg": 8,
        "net_weight_kg": 6,
        "system_code": "DL8801",
        "shipment_number": "AR085",
        "status": "AT AIRPORT",
        "date_received": "2026-10-05",
    }
    data.update(overrides)
    return data


def test_dashboard_counts_and_is_admin_only(client):
    login(client)
    sea = client.post("/api/sea", json=sea_payload(cartons=4))
    assert sea.status_code == 200, sea.text
    air = client.post("/api/air", json=air_payload())
    assert air.status_code == 200, air.text
    exit_row = client.post(
        "/api/exit",
        json={"supplier": "Exit Supplier", "confirm_new_supplier": True, "status": "Pending", "cartons": 3},
    )
    assert exit_row.status_code == 200, exit_row.text

    body = client.get("/api/dashboard")
    assert body.status_code == 200, body.text
    summary = body.json()
    assert summary["sea"]["rows"] == 1
    assert summary["sea"]["cartons"] == 4
    assert next(item for item in summary["sea"]["breakdown"] if item["label"] == "STAGE 1")["count"] == 1
    assert summary["air"]["rows"] == 1
    assert next(item for item in summary["air"]["breakdown"] if item["label"] == "AT AIRPORT")["count"] == 1
    assert summary["exit"]["rows"] == 1
    assert summary["exit"]["cartons"] == 3

    created = client.post("/api/users", json={"email": "op@example.com", "password": "password1", "role": "operator"})
    assert created.status_code == 200, created.text
    client.post("/api/auth/logout")
    login(client, "op@example.com", "password1")
    assert client.get("/api/dashboard").status_code == 403
    listed = client.get("/api/shipments")
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 2
    assert {row["kind"] for row in listed.json()["items"]} == {"sea", "air"}


def test_shipment_search_hides_deleted_rows(client):
    login(client)
    created = client.post("/api/sea", json=sea_payload(shipment_number="D4401", system_code="DL4401"))
    assert created.status_code == 200, created.text
    item_id = created.json()["item"]["id"]
    client.post("/api/air", json=air_payload())

    sea_only = client.get("/api/shipments", params={"q": "D4401", "kind": "sea"})
    assert sea_only.status_code == 200, sea_only.text
    assert sea_only.json()["total"] == 1
    assert sea_only.json()["items"][0]["progress"] == "STAGE 1"
    assert sea_only.json()["items"][0]["shipping_route"] == "IRAN"

    airport = client.get("/api/shipments", params={"progress": "AT AIRPORT"})
    assert airport.json()["total"] == 1
    assert airport.json()["items"][0]["kind"] == "air"
    assert airport.json()["items"][0]["shipment_number"] == "AR085"

    deleted = client.delete(f"/api/sea/{item_id}")
    assert deleted.status_code == 200, deleted.text
    hidden = client.get("/api/shipments", params={"q": "D4401"})
    assert hidden.json()["total"] == 0
