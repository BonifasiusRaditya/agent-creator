import json

import httpx

from conftest import project
from trendforge import integrations


def test_compatible_ai_ideas_and_brief_are_validated_and_persisted(client, monkeypatch):
    calls = []

    def provider(request):
        body = json.loads(request.content)
        calls.append(body)
        assert request.headers["authorization"] == "Bearer test-provider-key"
        assert "untrusted" in body["messages"][0]["content"]
        context = json.loads(body["messages"][1]["content"])
        if "selected_idea" not in context:
            result = {"ideas": [{"id": f"idea_{i}", "title": f"Test idea {i}", "angle": "A useful test angle for this audience.", "hook": "A short test hook."} for i in range(1, 4)]}
        else:
            result = {"title": "A test-generated story", "hook": "Start with one priority.", "angle": "A practical test story for students.",
                "script": "Choose one priority, remove a distraction, and spend a focused session on the task.", "cta": "Try it today.",
                "shots": [{"visual": "A test visual direction.", "narration": "A test spoken line.", "duration_seconds": 10} for _ in range(3)]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})

    actual_client = httpx.AsyncClient
    transport = httpx.MockTransport(provider)
    monkeypatch.setattr(integrations.httpx, "AsyncClient", lambda **kwargs: actual_client(transport=transport, **kwargs))
    client.patch("/api/v1/settings", json={"ai_base_url": "https://provider.example/v1", "ai_model": "test-model", "ai_api_key": "test-provider-key"})
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    response = client.post(base + "/ai/ideas", json={"source_video_ids": [], "expected_project_revision": p["revision"]})
    assert response.status_code == 200, response.text
    assert len(response.json()["ideas"]) == 3
    current = client.get(base).json()
    result = client.post(base + "/ai/brief", json={"idea_id": "idea_1", "expected_project_revision": current["revision"]})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "draft"
    assert result.json()["source_video_ids"] == []
    assert client.get(base).json()["brief"]["script"].startswith("Choose one priority")
    assert len(calls) == 2


def test_invalid_ai_response_cannot_be_approved_as_a_brief(client, monkeypatch):
    actual_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [{"message": {"content": '{"ideas":[]}'}}]}))
    monkeypatch.setattr(integrations.httpx, "AsyncClient", lambda **kwargs: actual_client(transport=transport, **kwargs))
    client.patch("/api/v1/settings", json={"ai_base_url": "https://provider.example/v1", "ai_model": "test-model"})
    p = project(client)
    response = client.post(f"/api/v1/projects/{p['id']}/ai/ideas", json={"source_video_ids": []})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_INVALID_RESPONSE"
    assert client.get(f"/api/v1/projects/{p['id']}").json()["ideas"] == []

