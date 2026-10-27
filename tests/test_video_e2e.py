import subprocess
import time
from pathlib import Path

import pytest

from conftest import approve, brief, project
from trendforge.media import ffmpeg, probe


def wait_job(c, pid, jid, timeout=240):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = c.get(f"/api/v1/projects/{pid}/jobs/{jid}").json()
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            assert job["status"] == "succeeded", job
            return job
        time.sleep(0.3)
    raise AssertionError("Video job did not finish within the test limit")


@pytest.mark.parametrize("count,target", [(3, 30), (5, 60)])
def test_real_upload_prepare_subtitle_export_download_delete(client, tmp_path, count, target):
    p = project(client, target)
    pid = p["id"]
    base = f"/api/v1/projects/{pid}"
    b = brief(client, p)
    approve(client, pid, "briefs", b["id"])
    length = target / count
    colors = ["0xA6B6D9", "0x6F8BC4", "0xB9C7E4", "0x8696B2", "0xCED6E8"]
    for index in range(count):
        clip = tmp_path / f"test-{index}.mp4"
        # Synthetic, test-owned images and silence: no real footage or invented speech.
        size = "640x360" if index % 2 else "360x640"
        args = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c={colors[index]}:s={size}:r=24"]
        if index % 2:
            args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
        args += ["-t", str(length), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
        if index % 2:
            args += ["-c:a", "aac"]
        subprocess.run(args + [str(clip)], check=True, capture_output=True)
        with clip.open("rb") as f:
            response = client.post(base + "/assets", files={"file": (clip.name, f, "video/mp4")}, data={"rights_confirmed": "true"})
        assert response.status_code == 201, response.text
    p = client.get(base).json()
    plan = client.post(base + "/plans/auto", json={"expected_project_revision": p["revision"]})
    assert plan.status_code == 201, plan.text
    approve(client, pid, "plans", plan.json()["id"])
    headers = {"Idempotency-Key": "test-prepare-request"}
    start = client.post(base + "/prepare-jobs", headers=headers, json={"plan_id": plan.json()["id"]})
    assert start.status_code == 202, start.text
    jid = start.json()["id"]
    duplicate = client.post(base + "/prepare-jobs", headers=headers, json={"plan_id": plan.json()["id"]})
    assert duplicate.status_code == 202 and duplicate.json()["id"] == jid
    assert client.patch(base, json={"goal": "Not while processing"}).status_code == 409
    wait_job(client, pid, jid)
    p = client.get(base).json()
    assert p["subtitle"]["speech_status"] == "no_speech"
    assert p["subtitle"]["cues"] == []
    rejected = client.post(base + f"/subtitles/{p['subtitle_id']}/approve", json={"expected_project_revision": p["revision"], "confirmation": True})
    assert rejected.status_code == 422
    approve(client, pid, "subtitles", p["subtitle_id"], no_speech_decision=True)
    exported = client.post(base + "/export-jobs", headers={"Idempotency-Key": "test-export-request"}, json={})
    assert exported.status_code == 202
    job = wait_job(client, pid, exported.json()["id"])
    eid = job["output"]["export_id"]
    assert client.post(base + "/ready-confirmation", json={"export_id": eid, "confirmation": True}).status_code == 422
    download = client.get(base + f"/exports/{eid}/files/mp4?download=true")
    assert download.status_code == 200 and len(download.content) > 5000
    saved = tmp_path / "finished.mp4"
    saved.write_bytes(download.content)
    meta = probe(saved)
    assert (meta["width"], meta["height"], meta["fps"]) == (1080, 1920, 30)
    assert abs(meta["duration_seconds"] - target) <= 0.12
    assert meta["video_codec"] == "h264" and meta["audio_codec"] == "aac"
    assert meta["sample_rate"] == 48000 and meta["audio_channels"] == 2
    ready = client.post(base + "/ready-confirmation", json={"export_id": eid, "confirmation": True})
    assert ready.status_code == 200 and ready.json()["phase"] == "USER_CONFIRMED_READY"
    assert client.get(base + f"/exports/{eid}/files/srt").status_code == 404
    if count == 3:
        # Exercise the actual subtitle renderer independently from ASR accuracy.
        p = client.get(base).json()
        captions = client.post(base + "/subtitles", json={"draft_id": p["draft_id"],
            "cues": [{"id": "render-test", "start_seconds": 1, "end_seconds": 4, "text": "Subtitle rendering test."}],
            "speech_status": "speech", "expected_project_revision": p["revision"]})
        assert captions.status_code == 201, captions.text
        approve(client, pid, "subtitles", captions.json()["id"])
        second = client.post(base + "/export-jobs", headers={"Idempotency-Key": "test-caption-export"}, json={})
        second_job = wait_job(client, pid, second.json()["id"])
        second_id = second_job["output"]["export_id"]
        srt = client.get(base + f"/exports/{second_id}/files/srt?download=true")
        assert "Subtitle rendering test." in srt.text
        rendered = client.get(base + f"/exports/{second_id}/files/mp4?download=true")
        rendered_path = tmp_path / "with-subtitles.mp4"
        rendered_path.write_bytes(rendered.content)
        import av
        import numpy as np
        with av.open(str(rendered_path)) as video:
            frame = next(f for f in video.decode(video=0) if float(f.time or 0) >= 2)
            image = frame.to_ndarray(format="rgb24")
        assert np.all(image[1400:1650, 108:972] > 235, axis=2).sum() > 100, "No rendered subtitle text found"
        versions = client.get(base + "/exports").json()
        assert len(versions) == 2
        assert sum(v["current"] for v in versions) == 1
    p = client.get(base).json()
    deleted = client.request("DELETE", base, json={"confirmation": True, "expected_project_revision": p["revision"]})
    assert deleted.status_code == 204, deleted.text
    assert client.get(base).status_code == 404

