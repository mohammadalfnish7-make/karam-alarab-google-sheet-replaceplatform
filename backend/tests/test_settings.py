from sqlalchemy import select

from app.check_read import read_check_file
from app.database import SessionLocal
from app.models import PromptKey, PromptVersion, User
from app.prompt_defaults import PROMPT_CATALOG
from app.prompt_store import get_active_prompt


def _login(client, email="admin@example.com", password="change-me"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def test_settings_are_admin_only(client):
    _login(client)
    created = client.post(
        "/api/users",
        json={"email": "op@example.com", "password": "password1", "role": "operator"},
    )
    assert created.status_code == 200, created.text

    ok = client.get("/api/settings")
    assert ok.status_code == 200
    body = ok.json()
    assert len(body["prompts"]) == len(PROMPT_CATALOG)
    assert "llm_model" in body["app"]

    client.post("/api/auth/logout")
    _login(client, "op@example.com", "password1")
    denied = client.get("/api/settings")
    assert denied.status_code == 403


def test_save_prompt_increments_version_and_runtime_uses_it(client, monkeypatch):
    _login(client)
    monkeypatch.setattr("app.agents.llm.settings.llm_provider", "anthropic")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.anthropic_api_key", "test-key")

    import json

    class _Response:
        def __init__(self, body):
            self._body = body
            self.status_code = 200
            self.text = json.dumps(body)

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    payload = json.dumps(
        {
            "company_name": "Acme",
            "date": "2026-10-01",
            "mark": "TL4455",
            "cartons": 2,
            "goods": "Perfume",
            "party": None,
        }
    )

    def fake_post(url, headers, json, timeout):
        return _Response({"content": [{"type": "text", "text": payload}], "stop_reason": "end_turn"})

    monkeypatch.setattr("app.agents.providers.anthropic.httpx.post", fake_post)

    first = client.get("/api/settings/prompts/intake.note")
    assert first.status_code == 200
    assert first.json()["active_version"] == 1

    updated = client.put(
        "/api/settings/prompts/intake.note",
        json={"body": "CUSTOM NOTE PROMPT for tests. Return JSON.", "note": "test edit"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["active_version"] == 2
    assert len(updated.json()["versions"]) == 2
    assert get_active_prompt("intake.note").startswith("CUSTOM NOTE PROMPT")

    db = SessionLocal()
    try:
        admin_id = db.scalar(select(User.id))
    finally:
        db.close()
    fields = read_check_file(b"%PDF-1.4 test", "application/pdf", "delivery_note", actor_user_id=admin_id)
    assert fields["company_name"] == "Acme"

    from app.models import AgentRun

    db = SessionLocal()
    try:
        run = db.scalar(select(AgentRun))
        assert run.input_json["prompt"].startswith("CUSTOM NOTE PROMPT")
    finally:
        db.close()


def test_rollback_restores_prior_active_without_deleting_history(client):
    _login(client)
    client.put(
        "/api/settings/prompts/intake.scale",
        json={"body": "Scale prompt version two.", "note": "v2"},
    )
    client.put(
        "/api/settings/prompts/intake.scale",
        json={"body": "Scale prompt version three.", "note": "v3"},
    )
    current = client.get("/api/settings/prompts/intake.scale")
    assert current.json()["active_version"] == 3
    assert get_active_prompt("intake.scale") == "Scale prompt version three."

    rolled = client.post("/api/settings/prompts/intake.scale/rollback", json={"version": 2})
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["active_version"] == 2
    assert len(rolled.json()["versions"]) == 3
    assert get_active_prompt("intake.scale") == "Scale prompt version two."

    db = SessionLocal()
    try:
        versions = db.scalars(
            select(PromptVersion)
            .where(PromptVersion.prompt_key == "intake.scale")
            .order_by(PromptVersion.version)
        ).all()
        assert [v.version for v in versions] == [1, 2, 3]
        key = db.get(PromptKey, "intake.scale")
        assert key.active_version_id == versions[1].id
    finally:
        db.close()


def test_update_app_settings(client):
    _login(client)
    response = client.put(
        "/api/settings/app",
        json={"llm_model": "claude-sonnet-4-5", "llm_timeout_sec": 90},
    )
    assert response.status_code == 200, response.text
    assert response.json()["app"]["llm_model"] == "claude-sonnet-4-5"
    assert response.json()["app"]["llm_timeout_sec"] == "90"

    listed = client.get("/api/settings")
    assert listed.json()["app"]["llm_model"] == "claude-sonnet-4-5"
