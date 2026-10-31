from conftest import approve, brief, project, upload_video
from test_workbuddy import connector_headers


def test_sessions_csrf_origin_and_secret_redaction(client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/session").json()["authenticated"]
    original = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/projects", json={}).status_code == 403
    client.headers["X-CSRF-Token"] = original
    assert client.post("/api/v1/projects", json={}, headers={"Origin": "https://other.example"}).status_code == 403
    response = client.patch("/api/v1/settings", json={"ai_api_key": "test-secret-never-returned", "ai_model": "test-model", "ai_base_url": "https://provider.example/v1"})
    assert response.status_code == 200
    assert "test-secret-never-returned" not in response.text
    assert response.json()["ai_key_configured"]
    assert "test-secret-never-returned" not in (client.app.state.settings.path).read_bytes().decode("ascii")
    assert client.post("/api/v1/settings/connector").status_code == 200
    client.cookies.clear()
    assert client.get("/api/v1/projects").status_code == 401


def test_human_approval_source_validation_and_revisions(client):
    p = project(client)
    b = brief(client, p)
    headers = connector_headers(client)
    assert client.post(f"/api/v1/projects/{p['id']}/briefs/{b['id']}/approve", headers=headers,
        json={"expected_project_revision": 2, "confirmation": True}).status_code == 403
    approve(client, p["id"], "briefs", b["id"])
    result = client.patch(f"/api/v1/projects/{p['id']}", json={"expected_project_revision": 1, "goal": "A changed goal"})
    assert result.status_code == 409
    payload = {k: v for k, v in b.items() if k in {"title", "hook", "angle", "script", "cta", "shots", "selected_idea_id"}}
    payload.update(source_video_ids=["fake-source"], expected_project_revision=client.get(f"/api/v1/projects/{p['id']}").json()["revision"])
    assert client.post(f"/api/v1/projects/{p['id']}/briefs", json=payload).status_code == 422


def test_manual_research_and_missing_credentials_are_honest(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    missing = client.post(base + "/research", json={"query": "Study habits"})
    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "YOUTUBE_NOT_CONFIGURED"
    manual = client.post(base + "/research", json={"query": "My own topic", "source_mode": "manual"})
    assert manual.json()["items"] == []
    assert manual.json()["data_mode"] == "manual"
    ideas = client.post(base + "/ai/ideas", json={"source_video_ids": []})
    assert ideas.status_code == 202
    assert ideas.json()["engine"] == "workbuddy"
    assert ideas.json()["status"] == "pending"
    assert client.get(base).json()["ideas"] == []  # Waiting is never fabricated AI output.


def test_invalid_media_and_cross_project_access(client):
    p = project(client)
    b = brief(client, p)
    approve(client, p["id"], "briefs", b["id"])
    rejected = upload_video(client, p["id"], b"not a video", "bad.mp4", expect="rejected")
    assert rejected["error"]["code"] == "INVALID_MEDIA"
    assert client.get(f"/api/v1/projects/{p['id']}/assets").json() == []
    # The rejected file is removed from storage.
    assert not any(client.app.state.storage.list(f"projects/{p['id']}"))
    second = project(client)
    assert client.get(f"/api/v1/projects/{second['id']}/briefs/{b['id']}").status_code == 404
    assert client.request("DELETE", f"/api/v1/projects/{p['id']}", json={"confirmation": False}).status_code in {400, 422}

