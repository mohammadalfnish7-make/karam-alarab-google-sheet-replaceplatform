import base64
import json

import pytest

from app.agents.providers import anthropic
from app.errors import AppError


class _Response:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code
        self.text = json.dumps(body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise anthropic.httpx.HTTPStatusError(
                "error",
                request=anthropic.httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
                response=anthropic.httpx.Response(self.status_code, text=self.text),
            )

    def json(self):
        return self._body


def test_anthropic_reads_image(monkeypatch):
    monkeypatch.setattr("app.agents.providers.anthropic.settings.anthropic_api_key", "test-key")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.llm_model", "claude-haiku-5-5")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.llm_timeout_sec", 30)
    text = json.dumps(
        {
            "mark": "TL4455",
            "cartons": 6,
            "total_weight_kg": 122.5,
            "pallet_weight_kg": 15,
            "scale_weight_kg": 122.5,
        }
    )

    def fake_post(url, headers, json=None, timeout=None):
        body = json
        assert url.endswith("/v1/messages")
        assert headers["x-api-key"] == "test-key"
        assert body["model"] == "claude-haiku-5-5"
        assert body["messages"][0]["content"][0]["type"] == "image"
        assert timeout == 30
        return _Response({"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"})

    monkeypatch.setattr("app.agents.providers.anthropic.httpx.post", fake_post)
    result = anthropic.AnthropicProvider().generate_content(
        prompt="scale",
        file_bytes=b"\xff\xd8\xff",
        mime="image/jpeg",
        max_tokens=2048,
    )
    assert "TL4455" in result["text"]
    assert result["finish"] == "end_turn"


def test_anthropic_reads_pdf_as_document(monkeypatch):
    monkeypatch.setattr("app.agents.providers.anthropic.settings.anthropic_api_key", "test-key")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.llm_model", "claude-haiku-5-5")

    def fake_post(url, headers, json=None, timeout=None):
        block = json["messages"][0]["content"][0]
        assert block["type"] == "document"
        assert block["source"]["media_type"] == "application/pdf"
        assert block["source"]["data"] == base64.b64encode(b"%PDF-1.4").decode("ascii")
        return _Response({"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn"})

    monkeypatch.setattr("app.agents.providers.anthropic.httpx.post", fake_post)
    anthropic.AnthropicProvider().generate_content(
        prompt="note",
        file_bytes=b"%PDF-1.4",
        mime="application/pdf",
        max_tokens=1024,
    )


def test_anthropic_requires_key(monkeypatch):
    monkeypatch.setattr("app.agents.providers.anthropic.settings.anthropic_api_key", "")
    with pytest.raises(AppError) as caught:
        anthropic.AnthropicProvider().generate_content(
            prompt="x",
            file_bytes=b"\xff\xd8\xff",
            mime="image/jpeg",
            max_tokens=100,
        )
    assert caught.value.status == 503
    assert "ANTHROPIC_API_KEY" in caught.value.body["message"]
