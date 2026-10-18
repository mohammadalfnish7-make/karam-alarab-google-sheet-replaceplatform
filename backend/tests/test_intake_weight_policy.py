from sqlalchemy import select

from app.database import SessionLocal
from app.intake_checks import (
    SCALE_VS_HANDWRITE_TOLERANCE,
    intake_save_gate,
    preferred_photo_totals,
    scale_vs_hand_detail,
)
from app.models import AgentRun, AuditLog, SeaCargo
from tests.conftest import login, sea_payload


def test_scale_vs_hand_tones():
    assert scale_vs_hand_detail({"scale_weight_kg": 100, "total_weight_kg": 100})["tone"] == "match"
    assert scale_vs_hand_detail({"scale_weight_kg": 100, "total_weight_kg": 100.05})["tone"] == "match"
    warn = scale_vs_hand_detail({"scale_weight_kg": 100, "total_weight_kg": 101})
    assert warn["tone"] == "warn"
    assert warn["label"] == f"OK ≤ {SCALE_VS_HANDWRITE_TOLERANCE:g} kg"
    conflict = scale_vs_hand_detail({"scale_weight_kg": 869, "total_weight_kg": 8869})
    assert conflict["tone"] == "conflict"
    assert conflict["label"] == "Conflict"


def test_preferred_totals_use_hand_tw_then_net():
    photos = [
        {"scale_weight_kg": 869, "total_weight_kg": 869, "pallet_weight_kg": 20, "cartons": 10},
        {"scale_weight_kg": 100, "total_weight_kg": 100, "pallet_weight_kg": 5, "cartons": 5},
    ]
    preferred = preferred_photo_totals(photos)
    assert preferred["cartons"] == 15
    assert preferred["total_weight_kg"] == 969
    assert preferred["pallet_weight_kg"] == 25
    assert preferred["net_weight_kg"] == 944


def test_save_gate_blocks_conflict_and_requires_warn_confirm():
    conflict = intake_save_gate(
        [{"status": "done", "extracted": {"scale_weight_kg": 869, "total_weight_kg": 8869}}]
    )
    assert conflict["can_save"] is False
    assert any("Conflict" in line for line in conflict["blockers"])

    warn = intake_save_gate(
        [{"status": "done", "extracted": {"scale_weight_kg": 100, "total_weight_kg": 101}}]
    )
    assert warn["can_save"] is False
    assert warn["needs_warn_confirm"] is True

    confirmed = intake_save_gate(
        [
            {
                "status": "done",
                "extracted": {"scale_weight_kg": 100, "total_weight_kg": 101},
                "warn_confirmed": True,
            }
        ]
    )
    assert confirmed["can_save"] is True

    reading = intake_save_gate([{"status": "reading", "extracted": {}}])
    assert reading["can_save"] is False


def test_sea_save_intake_check_sets_needs_review_and_audit(client):
    login(client)
    intake_check = {
        "confirm_weight_gap": True,
        "scale_overridden": True,
        "preferred": {
            "cartons": 10,
            "total_weight_kg": 100,
            "pallet_weight_kg": 5,
            "net_weight_kg": 95,
        },
        "overrides": [
            {
                "field": "scale_weight_kg",
                "from": 999,
                "to": 100,
                "why": "use_hand",
                "at": "2026-10-17T00:00:00Z",
                "photo_id": "p1",
                "file_name": "scale.jpg",
            }
        ],
        "photos": [
            {
                "file_name": "scale.jpg",
                "original": {"scale_weight_kg": 999, "total_weight_kg": 100},
                "extracted": {"scale_weight_kg": 100, "total_weight_kg": 100},
                "warn_confirmed": True,
                "scale_overridden": True,
                "overrides": [],
                "scale_vs_hand": {"tone": "match", "delta": 0, "label": "Match"},
            }
        ],
    }
    created = client.post(
        "/api/sea",
        json=sea_payload(
            cartons=10,
            gross_weight_kg=100,
            net_weight_kg=95,
            intake_check=intake_check,
        ),
    )
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["needs_review"] is True

    db = SessionLocal()
    try:
        row = db.get(SeaCargo, item["id"])
        assert row is not None
        assert row.needs_review is True
        audit = db.execute(
            select(AuditLog).where(AuditLog.entity_type == "sea_cargo", AuditLog.entity_id == str(row.id))
        ).scalar_one()
        assert audit.after_json["intake_check"]["scale_overridden"] is True
        assert audit.after_json["intake_check"]["overrides"][0]["why"] == "use_hand"
        run = db.execute(select(AgentRun).where(AgentRun.agent_name == "intake.override")).scalar_one()
        assert run.entity_id == str(row.id)
        assert run.output_json["scale_overridden"] is True
        assert run.provider == "operator"
    finally:
        db.close()
