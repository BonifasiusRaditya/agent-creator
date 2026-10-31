import hashlib
import subprocess
import time

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from conftest import approve, brief, project, sign_up, upload_video, wait_upload
from trendforge.app import create_app
from trendforge.backup import BackupError, create_backup, restore_backup, snapshots
from trendforge.db import Database
from trendforge.media import ffmpeg
from trendforge.storage import LocalStorage, S3Storage

BUCKET = "trendforge-test-1250000000"
ENDPOINT = "https://s3.amazonaws.com"  # moto intercepts AWS endpoints; COS uses cos.<region>.myqcloud.com


def make_clip(path, seconds=3):
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=360x640:r=24",
                    "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)],
                   check=True, capture_output=True)
    return path


def project_with_clip(client, tmp_path):
    p = project(client)
    approve(client, p["id"], "briefs", brief(client, p)["id"])
    upload = upload_video(client, p["id"], make_clip(tmp_path / "clip.mp4"), "clip.mp4")
    return p, upload


def test_backup_delete_restore_drill_into_a_new_workspace(client, tmp_path):
    p, upload = project_with_clip(client, tmp_path)
    db, storage = client.app.state.db, client.app.state.storage
    asset = db.doc(p["id"], upload["asset_id"], "asset")
    vault = LocalStorage(tmp_path / "backup-disk")
    first = create_backup(db, storage, vault)
    assert first["objects_copied"] == len(first["objects"]) >= 1
    assert create_backup(db, storage, vault)["objects_copied"] == 0  # Incremental: nothing new to copy.
    # Disaster: the project is deleted (files and rows).
    current = client.get(f"/api/v1/projects/{p['id']}").json()
    assert client.request("DELETE", f"/api/v1/projects/{p['id']}", json={"confirmation": True,
        "expected_project_revision": current["revision"]}).status_code == 204
    assert storage.size(asset["file_ref"]) is None
    # Restore into a brand-new database and storage location.
    new_db = Database(tmp_path / "restored" / "trendforge.sqlite3", backend="sqlite")
    new_storage = LocalStorage(tmp_path / "restored")
    report = restore_backup(vault, new_db, new_storage, "latest")
    assert report["verification"]["ok"] and report["verification"]["files_checked"] >= 1
    assert new_db.project(p["id"])["niche"] == p["niche"]
    assert new_db.project_owner(p["id"]) == client.get("/api/v1/session").json()["user"]["id"]
    restored = new_storage.path(asset["file_ref"]).read_bytes()
    assert hashlib.sha256(restored).hexdigest() == asset["sha256"]
    with new_db.connect() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"] == 0  # Everyone signs in again.
    with pytest.raises(BackupError, match="not empty"):
        restore_backup(vault, new_db, new_storage, "latest")


def test_restore_detects_damage_and_retention_keeps_newest(client, tmp_path):
    p, upload = project_with_clip(client, tmp_path)
    db, storage = client.app.state.db, client.app.state.storage
    vault = LocalStorage(tmp_path / "vault")
    ids = [create_backup(db, storage, vault, keep=2)["snapshot"] for _ in range(3)]
    assert snapshots(vault) == ids[1:]
    asset = db.doc(p["id"], upload["asset_id"], "asset")
    vault.path(f"backups/objects/{asset['file_ref']}").write_bytes(b"tampered but same length?")
    new_db = Database(tmp_path / "r" / "trendforge.sqlite3", backend="sqlite")
    report = restore_backup(vault, new_db, LocalStorage(tmp_path / "r"), ids[-1])
    assert not report["verification"]["ok"]
    vault.path(f"backups/{ids[-1]}/database.json.gz").write_bytes(b"broken")
    with pytest.raises(BackupError, match="damaged"):
        restore_backup(vault, Database(tmp_path / "r2" / "db.sqlite3", backend="sqlite"), LocalStorage(tmp_path / "r2"), ids[-1])


@mock_aws
def test_s3_storage_operations_and_signed_links(tmp_path):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    store = S3Storage(BUCKET, "us-east-1", "test-id", "test-secret", ENDPOINT)
    source = tmp_path / "a.mp4"
    source.write_bytes(b"video-bytes")
    store.put_file("projects/prj_1/uploads/a.mp4", source, "video/mp4")
    store.put_file("projects\\prj_1\\uploads\\b.mp4", source)  # Windows-style refs from older data still work.
    assert store.size("projects/prj_1/uploads/a.mp4") == 11
    assert store.size("projects/prj_1/missing.mp4") is None
    assert sorted(k for k, _ in store.list("projects/prj_1")) == ["projects/prj_1/uploads/a.mp4", "projects/prj_1/uploads/b.mp4"]
    assert store.fetch("projects/prj_1/uploads/a.mp4", tmp_path / "scratch").read_bytes() == b"video-bytes"
    store.copy("projects/prj_1/uploads/a.mp4", "backups/objects/projects/prj_1/uploads/a.mp4")
    target = store.upload_target("projects/prj_1/uploads/c.mp4", 100, "video/mp4", "/unused")
    assert target["fields"]["key"] == "projects/prj_1/uploads/c.mp4" and "policy" in target["fields"]
    link = store.response("projects/prj_1/uploads/a.mp4", "video/mp4", "my clip.mp4")
    assert link.status_code == 307 and "X-Amz-Signature" in link.headers["location"]
    assert "attachment" in link.headers["location"]
    store.delete_prefix("projects/prj_1")
    assert list(store.list("projects/prj_1")) == []
    with pytest.raises(Exception):
        store.fetch("../outside", tmp_path)


@mock_aws
def test_website_on_cos_uploads_directly_and_redirects_downloads(tmp_path, monkeypatch):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    for name, value in {"TRENDFORGE_STORAGE_BACKEND": "cos", "TRENDFORGE_COS_BUCKET": BUCKET, "TRENDFORGE_COS_REGION": "us-east-1",
                        "TRENDFORGE_COS_SECRET_ID": "test-id", "TRENDFORGE_COS_SECRET_KEY": "test-secret",
                        "TRENDFORGE_COS_ENDPOINT": ENDPOINT}.items():
        monkeypatch.setenv(name, value)
    with TestClient(create_app(tmp_path / "data")) as client:
        sign_up(client)
        p = project(client)
        approve(client, p["id"], "briefs", brief(client, p)["id"])
        clip = make_clip(tmp_path / "clip.mp4").read_bytes()
        created = client.post(f"/api/v1/projects/{p['id']}/uploads", json={"filename": "clip.mp4", "size": len(clip),
                                                                           "purpose": "clip", "rights_confirmed": True}).json()
        target = created["target"]
        assert target["url"].startswith("https://") and target["fields"]["key"].startswith(f"projects/{p['id']}/uploads/")
        assert ENDPOINT.split("//")[1] in client.get("/").headers["content-security-policy"]
        # The browser posts the file straight to the bucket; the website never receives it.
        assert client.post(f"/api/v1/projects/{p['id']}/uploads/{created['upload']['id']}/file",
                           files={"file": ("clip.mp4", clip, "video/mp4")}).status_code == 409
        boto3.client("s3", region_name="us-east-1").put_object(Bucket=BUCKET, Key=target["fields"]["key"], Body=clip)
        assert client.post(f"/api/v1/projects/{p['id']}/uploads/{created['upload']['id']}/complete").status_code == 202
        upload = wait_upload(client, p["id"], created["upload"]["id"])
        assert upload["status"] == "valid", upload
        media = client.get(f"/api/v1/projects/{p['id']}/assets/{upload['asset_id']}/media", follow_redirects=False)
        assert media.status_code == 307 and BUCKET in media.headers["location"]
        # Deleting the project removes its objects from the bucket.
        current = client.get(f"/api/v1/projects/{p['id']}").json()
        client.request("DELETE", f"/api/v1/projects/{p['id']}", json={"confirmation": True, "expected_project_revision": current["revision"]})
        assert list(client.app.state.storage.list(f"projects/{p['id']}")) == []
        # Worker scratch files are temporary when videos live in object storage.
        time.sleep(0.2)
        assert not any((tmp_path / "data" / "jobs").glob("*/inputs"))


def test_queued_work_waits_for_a_separate_worker_and_survives_its_crash(client, tmp_path):
    db = client.app.state.db
    client.app.state.worker.stop()  # Act as an external deployment with no worker running yet.
    p = project(client)
    approve(client, p["id"], "briefs", brief(client, p)["id"])
    upload = upload_video(client, p["id"], make_clip(tmp_path / "clip.mp4"), "clip.mp4", wait=False)
    assert upload["status"] == "validating"  # Queued, not lost, while no worker is online.
    job = db.claim_job("light", "crashed-worker", lease_seconds=-1)  # A worker took it, then died.
    assert job and db.recover_expired_jobs() == 1
    assert db.job(job["id"])["error"]["code"] == "INTERRUPTED"
    # Other projects' video jobs are queued rather than refused while one runs.
    other = project(client)
    db.start_job(p["id"], "prepare", {"plan_id": "x"}, "first")
    db.start_job(other["id"], "prepare", {"plan_id": "y"}, "second")
    with pytest.raises(Exception, match="already processing"):
        db.start_job(p["id"], "export", {"draft_id": "z"}, "third")
