from datetime import datetime, timedelta, timezone

import pytest

from conftest import project
from trendforge.app import purge_expired_data
from trendforge.errors import AppError


def test_interrupted_jobs_and_request_identity_survive_model_changes(client):
    p = project(client)
    db = client.app.state.db
    job, fresh = db.start_job(p["id"], "prepare", {"plan_id": "plan_test", "speech_model": "base"}, "same-request")
    assert fresh
    assert client.patch(f"/api/v1/projects/{p['id']}", json={"goal": "A changed goal"}).status_code == 409
    db.interrupt_jobs()
    assert db.job(job["id"])["status"] == "failed"
    assert db.job(job["id"])["error"]["code"] == "INTERRUPTED"
    same, fresh = db.start_job(p["id"], "prepare", {"plan_id": "plan_test", "speech_model": "small"}, "same-request")
    assert not fresh and same["id"] == job["id"]
    assert same["input"]["speech_model"] == "base"
    with pytest.raises(AppError):
        db.start_job(p["id"], "prepare", {"plan_id": "different_plan"}, "same-request")


def test_expired_metadata_is_removed_from_all_saved_source_references(client):
    p = project(client)
    db = client.app.state.db
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    db.add_doc(p["id"], "research", {"fetched_at": old, "items": [{"video_id": "expired_id1", "title": "Expired reference"}]})
    brief = db.add_doc(p["id"], "brief", {"source_video_ids": ["expired_id1"]})
    db.update_project(p["id"], {"idea_source_video_ids": ["expired_id1"]})
    purge_expired_data(db, client.app.state.settings.directory)
    assert db.docs(p["id"], "research") == []
    assert db.doc(p["id"], brief["id"])["source_video_ids"] == []
    assert db.project(p["id"])["idea_source_video_ids"] == []


def test_oversize_request_is_rejected_before_multipart_parsing(client):
    p = project(client)
    r = client.post(f"/api/v1/projects/{p['id']}/assets", content=b"", headers={"Content-Length": str(102 * 1024 * 1024)})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "REQUEST_TOO_LARGE"

