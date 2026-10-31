from conftest import project
from test_workbuddy import brief_result, connector_headers, ideas_result
from trendforge.models import MAX_REFERENCES, REFERENCE_CONTEXT_FIELDS


def seed_research(c, p, count):
    """Save a live-looking research run with `count` references (no network)."""
    items = [{"video_id": f"testvid{i:04d}", "title": f"Test reference {i}", "channel_id": "test-channel",
              "channel_title": "Test channel", "published_at": "2026-10-25T00:00:00Z",
              "thumbnail_url": "https://i.ytimg.com/vi/test/hqdefault.jpg",
              "watch_url": f"https://www.youtube.com/watch?v=testvid{i:04d}", "duration_seconds": 45,
              "view_count": "1000", "like_count": None, "comment_count": None, "live_status": "none"}
             for i in range(count)]
    c.app.state.db.add_doc(p["id"], "research", {"query": "Study habits", "period_days": 7, "source_mode": "search",
        "language": "en", "region": "ID", "data_mode": "live", "items": items, "warnings": [],
        "fetched_at": "2026-10-31T00:00:00+00:00"})
    return [x["video_id"] for x in items]


def test_writing_requests_accept_ten_references_and_reject_eleven(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    ids = seed_research(client, p, 12)
    over = client.post(base + "/ai/ideas", json={"source_video_ids": ids[:MAX_REFERENCES + 1], "expected_project_revision": p["revision"]})
    assert over.status_code == 422
    assert over.json()["error"]["code"] == "TOO_MANY_REFERENCES"
    assert client.get(base).json()["agent_request"] is None
    direct = client.post(base + "/agent-requests", json={"task": "ideas", "source_video_ids": ids,
        "expected_project_revision": p["revision"]})
    assert direct.json()["error"]["code"] == "TOO_MANY_REFERENCES"
    # Duplicates are counted once, so ten distinct references plus a repeat are accepted.
    ok = client.post(base + "/ai/ideas", json={"source_video_ids": ids[:MAX_REFERENCES] + [ids[0]], "expected_project_revision": p["revision"]})
    assert ok.status_code == 202, ok.text
    assert ok.json()["source_video_ids"] == ids[:MAX_REFERENCES]


def test_connector_context_contains_only_compact_reference_fields(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    ids = seed_research(client, p, 3)
    task = client.post(base + "/ai/ideas", json={"source_video_ids": ids, "expected_project_revision": p["revision"]}).json()
    context = client.get(base + "/agent-requests/" + task["id"], headers=connector_headers(client)).json()["context"]
    assert len(context["references"]) == 3
    assert all(set(x) == set(REFERENCE_CONTEXT_FIELDS) for x in context["references"])
    assert "view_count" not in str(context) and "thumbnail_url" not in str(context)


def test_manual_and_connector_brief_saves_enforce_the_limit(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    ids = seed_research(client, p, 12)
    body = {**brief_result(), "expected_project_revision": p["revision"]}
    too_many = client.post(base + "/briefs", json={**body, "source_video_ids": ids})
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "TOO_MANY_REFERENCES"
    saved = client.post(base + "/briefs", json={**body, "source_video_ids": ids[:MAX_REFERENCES]})
    assert saved.status_code == 201, saved.text
    # The WorkBuddy brief path goes through the same validation.
    current = client.get(base).json()
    task = client.post(base + "/ai/ideas", json={"source_video_ids": ids[:2], "expected_project_revision": current["revision"]}).json()
    assert client.post(base + f"/agent-requests/{task['id']}/result", json=ideas_result(), headers=connector_headers(client)).status_code == 200


def test_mcp_get_project_compacts_research_metadata(client, monkeypatch):
    from trendforge import mcp_server
    p = project(client)
    seed_research(client, p, 2)
    full = client.get(f"/api/v1/projects/{p['id']}").json()
    assert "thumbnail_url" in full["research"][0]["items"][0]
    monkeypatch.setattr(mcp_server, "call", lambda method, path, *a, **k: client.get("/api/v1" + path).json())
    compact = mcp_server.get_project(p["id"])
    assert all(set(x) == set(REFERENCE_CONTEXT_FIELDS) for x in compact["research"][0]["items"])


def test_brief_saved_before_the_limit_can_still_be_edited(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    ids = seed_research(client, p, 12)
    db = client.app.state.db
    legacy = db.add_doc(p["id"], "brief", {**brief_result(), "source_video_ids": ids, "selected_idea_id": None, "status": "draft"})
    current = db.update_project(p["id"], {"brief_id": legacy["id"], "phase": "BRIEF_DRAFT"})
    edited = client.post(base + "/briefs", json={**brief_result(), "hook": "An edited hook",
        "source_video_ids": ids, "expected_project_revision": current["revision"]})
    assert edited.status_code == 201, edited.text
    # Choosing a different, still oversized, set is a new selection and must respect the limit.
    current = client.get(base).json()
    changed = client.post(base + "/briefs", json={**brief_result(), "source_video_ids": ids[1:],
        "expected_project_revision": current["revision"]})
    assert changed.json()["error"]["code"] == "TOO_MANY_REFERENCES"
