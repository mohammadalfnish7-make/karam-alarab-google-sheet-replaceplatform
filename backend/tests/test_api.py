from tests.conftest import login, sea_payload


def test_login_required(client):
    assert client.get("/api/sea").status_code == 401
    assert client.post("/api/sea", json={}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    login(client)
    assert client.get("/api/auth/me").json()["email"] == "admin@example.com"
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_bad_system_code(client):
    login(client)
    response = client.post("/api/sea", json=sea_payload(system_code="NO DL"))
    assert response.status_code == 422
    assert "system_code" in response.json()["field_errors"]


def test_dr_shipment_rejected(client):
    login(client)
    response = client.post("/api/sea", json=sea_payload(shipment_number="DR1238"))
    assert response.status_code == 422
    assert "shipment_number" in response.json()["field_errors"]


def test_sea_shipment_digits_normalize_to_d(client):
    login(client)
    digits = client.post("/api/sea", json=sea_payload(shipment_number="45", system_code="DL4545"))
    assert digits.status_code == 200, digits.text
    assert digits.json()["item"]["shipment_number"] == "D45"

    lower = client.post("/api/sea", json=sea_payload(shipment_number="d45", system_code="DL4546"))
    assert lower.status_code == 200, lower.text
    assert lower.json()["item"]["shipment_number"] == "D45"

    spaced = client.post("/api/sea", json=sea_payload(shipment_number="D 45", system_code="DL4547"))
    assert spaced.status_code == 200, spaced.text
    assert spaced.json()["item"]["shipment_number"] == "D45"


def test_blank_shipment_warns_and_saves(client):
    login(client)
    response = client.post("/api/sea", json=sea_payload(shipment_number=None, system_code="DL4600"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["item"]["shipment_number"] is None
    codes = [item["code"] for item in body["warnings"]]
    assert "SHIPMENT_BLANK" in codes


def test_next_sea_shipment_is_max_plus_one(client):
    from datetime import datetime, timezone

    from app.database import SessionLocal
    from app.models import SeaCargo

    login(client)
    empty = client.get("/api/sea/next-shipment")
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"shipment_number": "D1", "number": 1}

    first = client.post("/api/sea", json=sea_payload(shipment_number="45", system_code="DL4701"))
    assert first.status_code == 200, first.text
    assert first.json()["item"]["shipment_number"] == "D45"
    # A later row may take a smaller number. Gaps are normal.
    earlier = client.post("/api/sea", json=sea_payload(shipment_number="3", system_code="DL4702"))
    assert earlier.status_code == 200, earlier.text
    assert earlier.json()["item"]["shipment_number"] == "D3"

    deleted = client.post("/api/sea", json=sea_payload(shipment_number="D200", system_code="DL4703"))
    assert deleted.status_code == 200, deleted.text
    deleted_id = deleted.json()["item"]["id"]
    assert client.delete(f"/api/sea/{deleted_id}").status_code == 200

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.add(
            SeaCargo(
                legacy=True,
                needs_review=True,
                issues=[],
                shipment_number="DR9999",
                company_name="Legacy DR",
                gross_is_no_pallet=False,
                created_at=now,
            )
        )
        db.add(
            SeaCargo(
                legacy=True,
                needs_review=True,
                issues=[],
                shipment_number="999",
                company_name="Legacy digits",
                gross_is_no_pallet=False,
                created_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    nxt = client.get("/api/sea/next-shipment")
    assert nxt.status_code == 200, nxt.text
    assert nxt.json() == {"shipment_number": "D46", "number": 46}


def test_bad_stage_rejected(client):
    login(client)
    response = client.post("/api/sea", json=sea_payload(stage="STAGE 9"))
    assert response.status_code == 422
    assert "stage" in response.json()["field_errors"]


def test_blank_system_code_allowed(client):
    login(client)
    response = client.post("/api/sea", json=sea_payload(system_code=None))
    assert response.status_code == 200, response.text
    assert response.json()["item"]["system_code"] is None
    codes = [item["code"] for item in response.json().get("warnings") or []]
    assert "SYSTEM_CODE_BLANK" not in codes


def test_net_exceeds_gross_warns(client):
    login(client)
    response = client.post(
        "/api/sea",
        json=sea_payload(system_code="DL88001", shipment_number="D88001", gross_weight_kg=10, net_weight_kg=12),
    )
    assert response.status_code == 200, response.text
    codes = [item["code"] for item in response.json()["warnings"]]
    assert "NET_EXCEEDS_GROSS" in codes
    assert response.json()["item"]["net_weight_kg"] == 12


def test_new_company_requires_confirmation(client):
    login(client)
    before = client.get("/api/sea").json()["total"]
    rejected = client.post("/api/sea", json=sea_payload(company_name="Brand New Co", confirm_new_company=False))
    assert rejected.status_code == 422
    body = rejected.json()
    assert body["code"] == "NEW_VALUE_CONFIRMATION_REQUIRED"
    assert body["proposed"]["company_name"] == "Brand New Co"
    assert "company_name" in body["field_errors"]
    assert client.get("/api/sea").json()["total"] == before

    created = client.post("/api/sea", json=sea_payload(company_name="Brand New Co", confirm_new_company=True))
    assert created.status_code == 200, created.text
    assert created.json()["item"]["company_name"] == "Brand New Co"
    lookup = client.get("/api/lookups/companies", params={"q": "Brand New"}).json()
    assert any(row["name"] == "Brand New Co" for row in lookup)

    again = client.post(
        "/api/sea",
        json=sea_payload(
            company_name="brand new co",
            confirm_new_company=False,
            system_code="DL1002",
            shipment_number="D1002",
        ),
    )
    assert again.status_code == 200, again.text
    assert again.json()["item"]["company_name"] == "Brand New Co"


def test_soft_delete_hides_until_restore(client):
    login(client)
    created = client.post("/api/sea", json=sea_payload(company_name="Delete Co", system_code="DL44001"))
    assert created.status_code == 200, created.text
    item_id = created.json()["item"]["id"]
    assert client.delete(f"/api/sea/{item_id}").status_code == 200
    hidden = client.get("/api/sea", params={"q": "Delete Co"}).json()
    assert all(row["id"] != item_id for row in hidden["items"])
    visible = client.get("/api/sea", params={"q": "Delete Co", "include_deleted": "true"}).json()
    match = next(row for row in visible["items"] if row["id"] == item_id)
    assert match["deleted_at"]
    restored = client.post(f"/api/sea/{item_id}/restore")
    assert restored.status_code == 200, restored.text
    shown = client.get("/api/sea", params={"q": "Delete Co"}).json()
    assert any(row["id"] == item_id for row in shown["items"])


def test_audit_on_create_and_update(client):
    login(client)
    created = client.post("/api/sea", json=sea_payload(company_name="Audit Co", system_code="DL77001"))
    assert created.status_code == 200, created.text
    item_id = created.json()["item"]["id"]
    updated = client.patch(f"/api/sea/{item_id}", json={"cartons": 5})
    assert updated.status_code == 200, updated.text
    audits = client.get("/api/audit", params={"entity_type": "sea_cargo", "entity_id": str(item_id)}).json()
    actions = {row["action"]: row for row in audits["items"]}
    assert "create" in actions
    assert actions["create"]["changed_fields"]
    change = next(item for item in actions["update"]["changed_fields"] if item["field"] == "cartons")
    assert change["old"] == 1
    assert change["new"] == 5
    history = client.get(f"/api/sea/{item_id}/history").json()
    assert [row["action"] for row in history] == ["create", "update"]


def test_exit_assigns_number_and_normalizes_pending(client):
    login(client)
    missing = client.post("/api/exit", json={"invoice_no": "2026/001"})
    assert missing.status_code == 422
    assert "supplier" in missing.json()["field_errors"]
    created = client.post(
        "/api/exit",
        json={
            "supplier": "Exit Supplier",
            "confirm_new_supplier": True,
            "status": "PENDING",
            "invoice_no": "2026/001-002",
            "cartons": 3,
        },
    )
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["status"] == "Pending"
    assert item["no"] == 1
    assert item["supplier"] == "Exit Supplier"
