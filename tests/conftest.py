import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from trendforge.app import create_app
from trendforge.config import ENV_FILE, Settings
from trendforge.db import Database


@pytest.fixture(autouse=True)
def isolate_service_configuration(monkeypatch):
    # Tests never use an owner's actual service credentials or selected engine.
    for name in Settings.env_names.values():
        monkeypatch.delenv(name, raising=False)
    for name in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "TRENDFORGE_DATABASE_BACKEND"):
        monkeypatch.delenv(name, raising=False)
    # Test-only accounts: a shared invite code and one admin username.
    monkeypatch.setenv("TRENDFORGE_INVITE_CODE", INVITE_CODE)
    monkeypatch.setenv("TRENDFORGE_ADMIN_USERNAMES", "tester")
    # Local storage and the embedded worker, polling quickly so tests stay fast.
    for name in ("TRENDFORGE_STORAGE_BACKEND", "TRENDFORGE_WORKER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TRENDFORGE_WORKER_POLL_SECONDS", "0.1")
    monkeypatch.setenv("TRENDFORGE_WORKER_MAX_IDLE_SECONDS", "0.5")


INVITE_CODE = "test-only-invite-code"
PASSWORD = "test-only-password"


def sign_up(c, username="tester", password=PASSWORD):
    """Register an account on client `c` and keep its CSRF token."""
    response = c.post("/api/v1/auth/register", json={"username": username, "password": password, "invite_code": INVITE_CODE})
    assert response.status_code == 201, response.text
    c.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()["user"]


def another_user(c, username="other-user"):
    """A second, separately signed-in client on the same running application."""
    other = TestClient(c.app)
    sign_up(other, username)
    return other


@pytest.fixture
def client(tmp_path):
    application = create_app(tmp_path / "data")
    with TestClient(application) as c:
        sign_up(c)
        yield c


TEST_TURSO_URL = "TRENDFORGE_TEST_TURSO_DATABASE_URL"
TEST_TURSO_TOKEN = "TRENDFORGE_TEST_TURSO_AUTH_TOKEN"
TABLES = ("documents", "jobs", "events", "projects", "sessions", "api_tokens", "users", "login_failures")


def turso_test_credentials():
    """Return (url, token) for a dedicated Turso test database, or skip the test.

    Never runs against the application database configured in .env: the tests
    create and delete projects and start video jobs.
    """
    url, token = os.environ.get(TEST_TURSO_URL, "").strip(), os.environ.get(TEST_TURSO_TOKEN, "").strip()
    if not url or not token:
        pytest.skip(f"Set {TEST_TURSO_URL} and {TEST_TURSO_TOKEN} for a dedicated Turso test database.")
    app_url = (dotenv_values(ENV_FILE).get("TURSO_DATABASE_URL") or "").strip().rstrip("/")
    if app_url and url.rstrip("/") == app_url:
        pytest.fail(f"{TEST_TURSO_URL} points to the application database. Use a separate test database.")
    return url, token


def clear_test_database(url, token):
    database = Database("unused.sqlite3", backend="turso", url=url, token=token)
    with database.connect() as c:
        for table in TABLES:
            c.execute(f"DELETE FROM {table}")


@pytest.fixture(params=["sqlite", "turso"])
def backend_client(request, tmp_path, monkeypatch):
    """A signed-in client on local SQLite or on the dedicated Turso test database."""
    if request.param == "turso":
        url, token = turso_test_credentials()
        monkeypatch.setenv("TURSO_DATABASE_URL", url)
        monkeypatch.setenv("TURSO_AUTH_TOKEN", token)
        monkeypatch.setenv("TRENDFORGE_DATABASE_BACKEND", "turso")
        clear_test_database(url, token)
    application = create_app(tmp_path / "data")
    try:
        with TestClient(application) as c:
            assert c.app.state.db.backend == request.param
            sign_up(c)
            yield c
    finally:
        if request.param == "turso":
            clear_test_database(url, token)


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



def wait_upload(c, pid, uid, timeout=120):
    """Poll an upload until the worker has accepted or rejected it."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        upload = c.get(f"/api/v1/projects/{pid}/uploads/{uid}").json()
        if upload["status"] not in {"awaiting_upload", "validating"}:
            return upload
        time.sleep(0.1)
    raise AssertionError("The upload check did not finish in time")


def upload_video(c, pid, data, filename="clip.mp4", purpose="clip", expect="valid", wait=True):
    """Upload as the browser does: reserve, send the file, complete, then wait for the check."""
    content = data.read_bytes() if isinstance(data, Path) else data
    created = c.post(f"/api/v1/projects/{pid}/uploads", json={"filename": filename, "size": len(content),
                                                              "purpose": purpose, "rights_confirmed": True})
    assert created.status_code == 201, created.text
    upload, target = created.json()["upload"], created.json()["target"]
    sent = c.post(target["url"], data=target["fields"], files={"file": (filename, content, "video/mp4")})
    assert sent.status_code == 200, sent.text
    completed = c.post(f"/api/v1/projects/{pid}/uploads/{upload['id']}/complete")
    assert completed.status_code == 202, completed.text
    if not wait:
        return completed.json()
    result = wait_upload(c, pid, upload["id"])
    if expect:
        assert result["status"] == expect, result
    return result
