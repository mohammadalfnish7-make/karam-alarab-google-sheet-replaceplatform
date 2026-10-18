import json

from tests.conftest import login


class _Response:
    def __init__(self, body):
        self._body = body
        self.status_code = 200
        self.text = json.dumps(body)

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def test_read_batch_runs_files_in_parallel(client, monkeypatch):
    login(client)
    monkeypatch.setattr("app.agents.llm.settings.llm_provider", "anthropic")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.anthropic_api_key", "test-key")
    monkeypatch.setattr("app.agents.providers.anthropic.settings.llm_model", "claude-haiku-5-5")
    seen: list[int] = []

    def fake_post(url, headers, json=None, timeout=None):
        index = len(seen) + 1
        seen.append(index)
        payload = {
            "mark": f"TL{1000 + index}",
            "cartons": index,
            "total_weight_kg": 10 + index,
            "pallet_weight_kg": 1,
            "scale_weight_kg": 10 + index,
        }
        return _Response(
            {
                "content": [{"type": "text", "text": __import__("json").dumps(payload)}],
                "stop_reason": "end_turn",
            }
        )

    monkeypatch.setattr("app.agents.providers.anthropic.httpx.post", fake_post)
    response = client.post(
        "/api/intake/read-batch",
        data={"kind": "scale"},
        files=[
            ("files", ("a.jpg", b"\xff\xd8\xff" + b"a", "image/jpeg")),
            ("files", ("b.jpg", b"\xff\xd8\xff" + b"b", "image/jpeg")),
        ],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "scale"
    assert len(body["results"]) == 2
    assert all(row["error"] is None for row in body["results"])
    assert {row["fields"]["cartons"] for row in body["results"]} == {1, 2}
    assert len(seen) == 2
