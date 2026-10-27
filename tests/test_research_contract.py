import httpx

from conftest import project
from trendforge import integrations


def test_youtube_mapping_cache_and_unknown_statistics(client, monkeypatch):
    calls = []
    video_id = "abc123Def45"

    def youtube(request):
        calls.append(request)
        assert request.url.params["key"] == "test-only-youtube-key"
        snippet = {"title": "A test reference", "channelId": "test-channel", "channelTitle": "Test channel",
                   "publishedAt": "2026-10-25T00:00:00Z", "thumbnails": {}}
        if request.url.path.endswith("/search"):
            assert request.url.params["type"] == "video"
            assert request.url.params["regionCode"] == "ID"
            assert request.url.params["order"] == "viewCount"
            return httpx.Response(200, json={"items": [{"id": {"videoId": video_id}, "snippet": snippet}]})
        return httpx.Response(200, json={"items": [{"id": video_id, "snippet": snippet,
            "statistics": {"viewCount": "1234"}, "contentDetails": {"duration": "PT45S"}}]})

    actual = httpx.AsyncClient
    transport = httpx.MockTransport(youtube)
    monkeypatch.setattr(integrations.httpx, "AsyncClient", lambda **kwargs: actual(transport=transport, **kwargs))
    client.patch("/api/v1/settings", json={"youtube_api_key": "test-only-youtube-key"})
    p = project(client)
    url = f"/api/v1/projects/{p['id']}/research"
    first = client.post(url, json={"query": "Study habits"})
    assert first.status_code == 200, first.text
    item = first.json()["items"][0]
    assert item["watch_url"] == f"https://www.youtube.com/watch?v={video_id}"
    assert item["like_count"] is None
    assert item["duration_seconds"] == 45
    assert "test-only-youtube-key" not in first.text
    second = client.post(url, json={"query": "Study habits"})
    assert second.json()["data_mode"] == "cache"
    assert len(calls) == 2


def test_provider_quota_failure_is_recoverable_and_safe(client, monkeypatch):
    actual = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _: httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}}))
    monkeypatch.setattr(integrations.httpx, "AsyncClient", lambda **kwargs: actual(transport=transport, **kwargs))
    client.patch("/api/v1/settings", json={"youtube_api_key": "private-test-key"})
    p = project(client)
    response = client.post(f"/api/v1/projects/{p['id']}/research", json={"query": "Study habits"})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "YOUTUBE_QUOTA"
    assert "private-test-key" not in response.text
    assert client.get(f"/api/v1/projects/{p['id']}").json()["research"] == []

