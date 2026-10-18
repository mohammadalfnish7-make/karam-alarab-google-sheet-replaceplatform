import json

import pytest
from sqlalchemy import select

from app.check_read import read_check_file
from app.database import SessionLocal
from app.errors import AppError
from app.models import AgentRun, User


def _login(client, email="admin@example.com", password="change-me"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


class _Response:
    def __init__(self, body):
        self._body = body
        self.status_code = 200
        self.text = json.dumps(body)

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def test_intake_run_stores_prompt_model_text_and_parsed_fields(monkeypatch):
    monkeypatch.setattr("app.agents.llm.settings.llm_provider", "anthropic")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.anthropic_api_key", "test-key")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.llm_model", "claude-haiku-5-5")
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
        assert headers["x-api-key"] == "test-key"
        assert "messages" in url
        assert json["model"] == "claude-haiku-5-5"
        return _Response({"content": [{"type": "text", "text": payload}], "stop_reason": "end_turn"})

    monkeypatch.setattr("app.agents.providers.anthropic.httpx.post", fake_post)
    db = SessionLocal()
    try:
        admin_id = db.scalar(select(User.id))
    finally:
        db.close()
    fields = read_check_file(b"%PDF-1.4 test", "application/pdf", "delivery_note", actor_user_id=admin_id)
    assert fields["company_name"] == "Acme"
    assert fields["mark"] == "TL4455"

    db = SessionLocal()
    try:
        run = db.scalar(select(AgentRun))
        assert run is not None
        assert run.agent_name == "intake.delivery_note"
        assert run.status == "ok"
        assert run.actor_user_id == admin_id
        assert run.provider == "anthropic"
        assert run.model == "claude-haiku-5-5"
        assert run.duration_ms is not None
        assert run.duration_ms >= 0
        assert run.input_json["prompt"].startswith("Read this delivery note")
        assert run.input_json["byte_size"] == len(b"%PDF-1.4 test")
        assert "sha256" in run.input_json
        names = [step["name"] for step in run.steps_json]
        assert names == ["llm", "parse"]
        assert run.steps_json[0]["output"]["text"] == payload
        assert run.steps_json[0]["duration_ms"] is not None
        assert run.output_json["cartons"] == 2
        assert run.finished_at is not None
        assert run.error_stack is None
    finally:
        db.close()


def test_missing_key_is_stored_as_an_error_run(monkeypatch):
    monkeypatch.setattr("app.agents.llm.settings.llm_provider", "anthropic")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.anthropic_api_key", "")

    def fail_post(*_args, **_kwargs):
        raise AssertionError("Anthropic should not be called without a key")

    monkeypatch.setattr("app.agents.providers.anthropic.httpx.post", fail_post)
    with pytest.raises(AppError) as caught:
        read_check_file(b"photo", "image/jpeg", "scale")
    assert caught.value.status == 503

    db = SessionLocal()
    try:
        run = db.scalar(select(AgentRun))
        assert run.agent_name == "intake.scale"
        assert run.status == "error"
        assert "ANTHROPIC_API_KEY" in run.error_message
        assert "read_check_file" in run.error_stack
        assert run.steps_json == []
    finally:
        db.close()


def test_agent_runs_are_admin_only(client):
    _login(client)
    created = client.post(
        "/api/users",
        json={"email": "op@example.com", "password": "password1", "role": "operator"},
    )
    assert created.status_code == 200, created.text
    empty = client.get("/api/agent-runs")
    assert empty.status_code == 200
    assert empty.json()["total"] == 0

    client.post("/api/auth/logout")
    _login(client, "op@example.com", "password1")
    denied = client.get("/api/agent-runs")
    assert denied.status_code == 403
