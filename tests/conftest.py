from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trendforge.app import create_app
from trendforge.config import Settings


@pytest.fixture(autouse=True)
def isolate_service_configuration(monkeypatch):
    # Tests never use an owner's actual service credentials or selected engine.
    for name in Settings.env_names.values():
        monkeypatch.delenv(name, raising=False)
    for name in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "TRENDFORGE_DATABASE_BACKEND"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client(tmp_path):
    application = create_app(tmp_path / "data")
    with TestClient(application) as c:
        response = c.post("/api/v1/setup", json={"password": "test-only-password"})
        assert response.status_code == 200, response.text
        c.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield c


def project(c, duration=30):
    response = c.post("/api/v1/projects", json={"niche": "Test project — study tips", "audience": "Students",
        "goal": "Share one practical study habit", "target_duration_seconds": duration, "language": "en"})
    assert response.status_code == 201, response.text
    return response.json()


def brief(c, p):
    response = c.post(f"/api/v1/projects/{p['id']}/briefs", json={
        "title": "Test story", "hook": "Start with one priority.", "angle": "A practical, original study habit.",
        "script": "Start with one priority. Put your phone away. Work for one focused session.",
        "cta": "Try one focused session today.", "shots": [{"visual": "Test-owned synthetic clip", "narration": "A test spoken line.",
            "duration_seconds": p["target_duration_seconds"] / 3} for _ in range(3)],
        "expected_project_revision": p["revision"], "source_video_ids": []})
    assert response.status_code == 201, response.text
    return response.json()


def approve(c, pid, kind, did, **extra):
    p = c.get(f"/api/v1/projects/{pid}").json()
    response = c.post(f"/api/v1/projects/{pid}/{kind}/{did}/approve", json={
        "expected_project_revision": p["revision"], "confirmation": True, **extra})
    assert response.status_code == 200, response.text
    return response.json()

