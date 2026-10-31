import json
import sqlite3

from fastapi.testclient import TestClient

from conftest import INVITE_CODE, PASSWORD, another_user, approve, brief, project, sign_up
from test_workbuddy import connector_headers, ideas_result
from trendforge.db import Database


def register(c, username, invite=INVITE_CODE, password=PASSWORD):
    return c.post("/api/v1/auth/register", json={"username": username, "password": password, "invite_code": invite})


def login(c, username, password=PASSWORD):
    return c.post("/api/v1/session", json={"username": username, "password": password})


def test_registration_requires_the_shared_invite_code(client, monkeypatch):
    fresh = TestClient(client.app)
    assert fresh.get("/api/v1/session").json() == {"authenticated": False, "csrf_token": None, "user": None, "registration_open": True}
    wrong = register(fresh, "new-creator", invite="not-the-code")
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "INVALID_INVITE_CODE"
    assert register(fresh, "x", invite=INVITE_CODE).json()["error"]["code"] == "INVALID_USERNAME"
    assert register(fresh, "new-creator", password="short").json()["error"]["code"] == "INVALID_PASSWORD_FORMAT"
    created = register(fresh, "New-Creator")
    assert created.status_code == 201
    assert created.json()["user"]["username"] == "new-creator"
    assert created.json()["user"]["display_name"] == "New-Creator"
    assert fresh.get("/api/v1/session").json()["user"]["username"] == "new-creator"
    # Usernames are unique regardless of letter case.
    assert register(TestClient(client.app), "NEW-creator").json()["error"]["code"] == "USERNAME_TAKEN"
    monkeypatch.setenv("TRENDFORGE_INVITE_CODE", "")
    closed = register(TestClient(client.app), "late-creator")
    assert closed.status_code == 403 and closed.json()["error"]["code"] == "REGISTRATION_CLOSED"
    assert TestClient(client.app).get("/api/v1/session").json()["registration_open"] is False


def test_sign_in_is_generic_rate_limited_and_never_stores_plain_passwords(client):
    fresh = TestClient(client.app)
    unknown = login(fresh, "nobody-here")
    wrong = login(fresh, "tester", "a-wrong-password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]
    ok = login(fresh, "TESTER")
    assert ok.status_code == 200 and ok.json()["user"]["username"] == "tester"
    with client.app.state.db.connect() as c:
        stored = c.execute("SELECT password_hash FROM users WHERE username='tester'").fetchone()["password_hash"]
    assert PASSWORD not in stored
    for _ in range(5):
        assert login(TestClient(client.app), "tester", "a-wrong-password").status_code == 401
    locked = login(TestClient(client.app), "tester")
    assert locked.status_code == 429  # Locked even with the right password, for this account only.
    sign_up(TestClient(client.app), "unaffected")
    assert login(TestClient(client.app), "unaffected").status_code == 200


def test_sign_out_and_password_change_end_other_sessions(client):
    laptop = TestClient(client.app)
    laptop.headers["X-CSRF-Token"] = login(laptop, "tester").json()["csrf_token"]
    assert laptop.get("/api/v1/projects").status_code == 200
    bad = client.post("/api/v1/auth/password", json={"current_password": "wrong-password", "new_password": "a-new-password"})
    assert bad.status_code == 403
    changed = client.post("/api/v1/auth/password", json={"current_password": PASSWORD, "new_password": "a-new-password"})
    assert changed.status_code == 200
    assert laptop.get("/api/v1/projects").status_code == 401  # The other device was signed out.
    assert client.get("/api/v1/projects").status_code == 200  # This device stays signed in.
    assert login(TestClient(client.app), "tester").status_code == 401
    assert login(TestClient(client.app), "tester", "a-new-password").status_code == 200
    assert client.delete("/api/v1/session").status_code == 204
    assert client.get("/api/v1/projects").status_code == 401


def test_users_cannot_see_or_change_each_others_projects(client):
    p = project(client)
    b = brief(client, p)
    approve(client, p["id"], "briefs", b["id"])
    base = f"/api/v1/projects/{p['id']}"
    other = another_user(client)
    assert other.get("/api/v1/projects").json() == []
    for method, path, body in [("GET", base, None), ("GET", base + "/research", None), ("GET", base + f"/briefs/{b['id']}", None),
                               ("PATCH", base, {"goal": "Taking over this project"}), ("POST", base + "/ai/ideas", {}),
                               ("GET", base + "/assets", None), ("GET", base + "/exports", None),
                               ("DELETE", base, {"confirmation": True})]:
        response = other.request(method, path, json=body)
        assert response.status_code == 404, (method, path, response.text)
    own = project(other)
    assert [x["id"] for x in other.get("/api/v1/projects").json()] == [own["id"]]
    assert [x["id"] for x in client.get("/api/v1/projects").json()] == [p["id"]]
    assert client.get(base).json()["goal"] == p["goal"]


def test_connector_tokens_are_personal_and_revocable(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    task = client.post(base + "/ai/ideas", json={}).json()
    other = another_user(client)
    other_project = project(other)
    other.post(f"/api/v1/projects/{other_project['id']}/ai/ideas", json={})
    mine, theirs = connector_headers(client), connector_headers(other)
    # Each token lists only its owner's pending writing requests.
    assert [x["project_id"] for x in client.get("/api/v1/agent/requests", headers=mine).json()] == [p["id"]]
    assert [x["project_id"] for x in client.get("/api/v1/agent/requests", headers=theirs).json()] == [other_project["id"]]
    assert client.post(base + f"/agent-requests/{task['id']}/result", json=ideas_result(), headers=theirs).status_code == 404
    assert client.get("/api/v1/projects", headers=theirs).json()[0]["id"] == other_project["id"]
    # A connector cannot mint tokens or act as the human.
    bare = TestClient(client.app)
    assert bare.post("/api/v1/tokens", json={"label": "More"}, headers=mine).status_code == 403
    tokens = client.get("/api/v1/tokens").json()
    assert len(tokens) == 1 and "token" not in tokens[0] and "token_hash" not in tokens[0]
    assert client.request("DELETE", f"/api/v1/tokens/{tokens[0]['id']}").status_code == 204
    revoked = bare.get("/api/v1/projects", headers=mine)
    assert revoked.status_code == 401
    # Users cannot revoke someone else's token.
    their_token = other.get("/api/v1/tokens").json()[0]["id"]
    assert client.request("DELETE", f"/api/v1/tokens/{their_token}").status_code == 404


def test_shared_settings_are_admin_only(client):
    other = another_user(client)
    assert other.get("/api/v1/settings").json()["is_admin"] is False
    assert "storage_path" not in other.get("/api/v1/settings").json()
    refused = other.patch("/api/v1/settings", json={"speech_model": "tiny"})
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "ADMIN_REQUIRED"
    assert other.post("/api/v1/settings/speech-model", headers={"Idempotency-Key": "test-model"}).status_code == 403
    assert client.patch("/api/v1/settings", json={"speech_model": "tiny"}).status_code == 200


def test_existing_workspace_upgrades_and_old_projects_can_be_claimed(tmp_path, monkeypatch):
    path = tmp_path / "trendforge.sqlite3"
    with sqlite3.connect(path) as c:  # The schema before accounts existed.
        c.executescript("""CREATE TABLE projects(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE sessions(token_hash TEXT PRIMARY KEY, expires REAL NOT NULL, csrf TEXT NOT NULL);""")
        c.execute("INSERT INTO projects VALUES (?,?)", ("prj_legacy", json.dumps({"id": "prj_legacy", "niche": "Old project"})))
        c.execute("INSERT INTO sessions VALUES (?,?,?)", ("legacy-session", 9e12, "legacy-csrf"))
    database = Database(path, backend="sqlite")
    with database.connect() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"] == 0
    assert database.project_owner("prj_legacy") is None
    user = database.create_user("owner", "Owner", "test-hash", "ab" * 16)
    assert database.projects(owner_id=user["id"]) == []
    from scripts import claim_projects
    monkeypatch.setattr(claim_projects, "Database", lambda *a, **k: database)
    claim_projects.main(["--username", "owner"])
    assert database.project_owner("prj_legacy") is None  # Preview changes nothing.
    claim_projects.main(["--username", "Owner", "--apply"])
    assert [p["id"] for p in database.projects(owner_id=user["id"])] == ["prj_legacy"]
