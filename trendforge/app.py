import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import time
from collections import deque
from contextlib import suppress
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import Body, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import DATA, ROOT, STATIC, Settings
from .db import Database, new_id, now
from .errors import AppError
from .integrations import generate_brief, generate_ideas, pexels_search, provider_json, research_youtube, validate_base_url
from .media import MAX_FILE, MAX_TOTAL, MediaWorker, ffmpeg, validate_upload
from .models import Approval, BriefInput, PlanInput, ProjectInput, ResearchInput, SubtitleInput, allocate_segments, validate_cues


def public(value):
    if isinstance(value, dict):
        return {k: public(v) for k, v in value.items() if k not in {
            "file_ref", "audio_ref", "mp4_ref", "srt_ref", "input", "payload_hash", "password_hash", "service_token"}}
    if isinstance(value, list):
        return [public(v) for v in value]
    return value


def error_response(exc):
    return JSONResponse({"error": {"code": exc.code, "message": exc.message, "details": exc.details},
                         "request_id": new_id("req")}, status_code=exc.status)


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32).hex()


def purge_expired_data(db, directory):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    with db.connect() as c:
        expired_ids = set()
        for row in c.execute("SELECT id,data FROM documents WHERE kind='research'").fetchall():
            run = json.loads(row["data"])
            if run.get("fetched_at", "") < cutoff:
                expired_ids.update(x["video_id"] for x in run.get("items", []))
                c.execute("DELETE FROM documents WHERE id=?", (row["id"],))
        if expired_ids:
            for row in c.execute("SELECT id,data FROM documents WHERE kind='brief'").fetchall():
                doc = json.loads(row["data"])
                doc["source_video_ids"] = [x for x in doc.get("source_video_ids", []) if x not in expired_ids]
                c.execute("UPDATE documents SET data=? WHERE id=?", (json.dumps(doc), row["id"]))
            for row in c.execute("SELECT id,data FROM projects").fetchall():
                project = json.loads(row["data"])
                project["idea_source_video_ids"] = [x for x in project.get("idea_source_video_ids", []) if x not in expired_ids]
                c.execute("UPDATE projects SET data=? WHERE id=?", (json.dumps(project), row["id"]))
        c.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
    for log in directory.glob("jobs/*/process.log"):
        try:
            if log.stat().st_mtime < time.time() - 7 * 86400:
                log.unlink(missing_ok=True)
        except OSError:
            pass  # An active diagnostic may be in use; the next pass will retry.


def create_app(directory=None):
    directory = Path(directory or DATA).resolve()

    @asynccontextmanager
    async def lifespan(app):
        directory.mkdir(parents=True, exist_ok=True)
        settings = Settings(directory)
        db = Database(directory / "trendforge.sqlite3")
        app.state.settings, app.state.db = settings, db
        app.state.worker = MediaWorker(db, settings, directory)
        app.state.login_attempts = deque()
        app.state.research_lock = asyncio.Lock()
        # No stale external metadata is retained as a historical statistics archive.
        purge_expired_data(db, directory)

        async def cleanup_loop():
            while True:
                await asyncio.sleep(60)
                await asyncio.to_thread(purge_expired_data, db, directory)

        cleanup_task = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
            await asyncio.to_thread(app.state.worker.shutdown)

    app = FastAPI(title="TrendForge API", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(AppError)
    async def handle_error(_, exc):
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_, exc):
        return error_response(AppError("Check the highlighted fields and try again.", "VALIDATION_ERROR", details={
            "fields": [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]}))

    @app.middleware("http")
    async def security(request, call_next):
        path = request.url.path
        request.state.actor = None
        request.state.csrf = None
        if path.startswith("/api/"):
            try:
                origin = request.headers.get("origin")
                if origin and origin != str(request.base_url).rstrip("/"):
                    raise AppError("This request came from a different website.", "ORIGIN_REJECTED", 403)
                settings, db = app.state.settings, app.state.db
                bearer = request.headers.get("authorization", "")
                if bearer.startswith("Bearer ") and hmac.compare_digest(bearer[7:], settings.get("service_token")):
                    request.state.actor = "connector"
                else:
                    token = request.cookies.get("trendforge_session", "")
                    if token:
                        with db.connect() as c:
                            row = c.execute("SELECT * FROM sessions WHERE token_hash=? AND expires>?",
                                (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
                        if row:
                            request.state.actor = "operator"
                            request.state.csrf = row["csrf"]
                anonymous = path in {"/api/v1/session", "/api/v1/setup"}
                if not request.state.actor and not anonymous:
                    raise AppError("Sign in to continue.", "UNAUTHORIZED", 401)
                if request.method not in {"GET", "HEAD", "OPTIONS"} and request.state.actor == "operator":
                    if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), request.state.csrf or ""):
                        raise AppError("Your session needs a refresh. Reload the page and try again.", "CSRF_REJECTED", 403)
                size = request.headers.get("content-length", "0")
                limit = MAX_FILE + 1024 * 1024 if path.endswith("/assets") else 2 * 1024 * 1024
                if size.isdigit() and int(size) > limit:
                    raise AppError("This request is too large. Each video can be up to 100 MiB.", "REQUEST_TOO_LARGE", 413)
            except AppError as exc:
                return error_response(exc)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    def db():
        return app.state.db

    def operator(request):
        if request.state.actor != "operator":
            raise AppError("This action requires your confirmation in the website.", "HUMAN_APPROVAL_REQUIRED", 403)

    def safe_path(ref):
        path = (directory / ref).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise AppError("This file is no longer available.", "FILE_NOT_FOUND", 404)
        return path

    def _hydrate(pid):
        project = db().project(pid)
        for field, kind in (("brief", "brief"), ("plan", "plan"), ("draft", "draft"), ("subtitle", "subtitle")):
            did = project.get(field + "_id")
            project[field] = db().doc(pid, did, kind) if did else None
        project["assets"] = db().docs(pid, "asset")
        project["research"] = db().docs(pid, "research")
        project["exports"] = valid_exports(pid)
        project["active_job"] = db().active_job(pid)
        with db().connect() as c:
            row = c.execute("SELECT data FROM jobs WHERE project_id=? ORDER BY rowid DESC LIMIT 1", (pid,)).fetchone()
        project["last_job"] = json.loads(row["data"]) if row else None
        return public(project)

    def hydrate(pid):
        with db().lock:
            return _hydrate(pid)

    def valid_exports(pid):
        project = db().project(pid)
        return [{**x, "current": x["id"] == project.get("export_id")} for x in reversed(db().docs(pid, "export"))
                if db().job(x["job_id"])["status"] == "succeeded"]

    def invalidate(pid, level, expected=None):
        changes = {"export_id": None, "ready_confirmed_at": None}
        if level in {"brief", "asset"}:
            changes.update({"plan_id": None, "draft_id": None, "subtitle_id": None})
        elif level == "plan":
            changes.update({"draft_id": None, "subtitle_id": None})
        return changes

    def save_brief(pid, body):
        with db().lock:
            project = db().assert_editable(pid, body.expected_project_revision)
            known = {x["video_id"] for r in db().docs(pid, "research") for x in r.get("items", [])}
            if not set(body.source_video_ids).issubset(known):
                raise AppError("Choose references from this project's research. Sources cannot be invented.", "UNKNOWN_SOURCE")
            if abs(sum(s.duration_seconds for s in body.shots) - project["target_duration_seconds"]) > 0.1:
                raise AppError("Shot durations must add up to the selected video duration.", "BRIEF_DURATION_MISMATCH")
            content = body.model_dump(exclude={"expected_project_revision"})
            brief = db().add_doc(pid, "brief", {**content, "status": "draft"})
            db().update_project(pid, {**invalidate(pid, "brief"), "brief_id": brief["id"], "phase": "BRIEF_DRAFT"}, project["revision"])
            db().event(pid, "brief_saved", {"brief_id": brief["id"]})
            return public(brief)

    def save_plan(pid, body):
        with db().lock:
            project = db().assert_editable(pid, body.expected_project_revision)
            if body.brief_revision_id != project.get("brief_id"):
                raise AppError("Use the current approved brief.", "STALE_BRIEF", 409)
            brief = db().doc(pid, body.brief_revision_id, "brief")
            if brief["status"] != "approved":
                raise AppError("Approve your brief before creating the edit plan.", "APPROVAL_REQUIRED", 409)
            assets = {x["id"]: x for x in db().docs(pid, "asset")}
            if len(body.segments) != len(assets) or not 3 <= len(assets) <= 5:
                raise AppError("Use each of your 3–5 clips exactly once.")
            if {s.asset_id for s in body.segments} != set(assets) or sorted(s.order for s in body.segments) != list(range(1, len(assets) + 1)):
                raise AppError("Each clip and position must appear exactly once.")
            for segment in body.segments:
                if segment.out_seconds > assets[segment.asset_id]["duration_seconds"] + 0.01:
                    raise AppError("A trim point goes past the end of its clip.", "TRIM_OUT_OF_RANGE")
            total = sum(s.out_seconds - s.in_seconds for s in body.segments)
            if abs(total - body.target_duration_seconds) > 1 / 30 + 0.001 or body.target_duration_seconds != project["target_duration_seconds"]:
                raise AppError("The combined clip duration must match your target.", "PLAN_DURATION_MISMATCH")
            plan = db().add_doc(pid, "plan", {**body.model_dump(exclude={"expected_project_revision"}), "status": "draft"})
            db().update_project(pid, {**invalidate(pid, "plan"), "plan_id": plan["id"], "phase": "PLAN_DRAFT"}, project["revision"])
            return public(plan)

    def launch(pid, kind, snapshot, request):
        key = request.headers.get("idempotency-key")
        if not key or len(key) > 180:
            raise AppError("A unique request key is required to start processing.", "IDEMPOTENCY_KEY_REQUIRED")
        with db().lock:
            job, fresh = db().start_job(pid, kind, snapshot, key)
            if fresh:
                app.state.worker.submit(job)
        return public(job)

    def create_session(response):
        token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(24)
        with db().connect() as c:
            c.execute("INSERT INTO sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), time.time() + 86400, csrf))
        response.set_cookie("trendforge_session", token, httponly=True, samesite="strict", max_age=86400)
        return csrf

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/v1/session")
    def session(request: Request):
        return {"authenticated": request.state.actor == "operator", "csrf_token": request.state.csrf,
                "setup_required": not bool(app.state.settings.get("password_hash"))}

    @app.post("/api/v1/setup")
    def setup(response: Response, body: dict = Body(...)):
        with db().lock:
            if app.state.settings.get("password_hash"):
                raise AppError("This workspace has already been set up. Sign in instead.", "ALREADY_CONFIGURED", 409)
            password = body.get("password", "")
            if not isinstance(password, str) or not 8 <= len(password) <= 200:
                raise AppError("Choose a password between 8 and 200 characters.")
            salt = secrets.token_hex(16)
            app.state.settings.update({"password_hash": password_hash(password, salt), "password_salt": salt})
            return {"authenticated": True, "csrf_token": create_session(response)}

    @app.post("/api/v1/session")
    def sign_in(response: Response, body: dict = Body(...)):
        attempts = app.state.login_attempts
        while attempts and attempts[0] < time.monotonic() - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise AppError("Too many sign-in attempts. Try again in one minute.", "RATE_LIMIT", 429)
        attempts.append(time.monotonic())
        settings = app.state.settings
        password = body.get("password", "")
        if not settings.get("password_hash") or not isinstance(password, str) or len(password) > 200 or not hmac.compare_digest(password_hash(password, settings.get("password_salt")), settings.get("password_hash")):
            raise AppError("The password is incorrect.", "INVALID_PASSWORD", 401)
        return {"authenticated": True, "csrf_token": create_session(response)}

    @app.delete("/api/v1/session", status_code=204)
    def sign_out(request: Request, response: Response):
        token = request.cookies.get("trendforge_session", "")
        with db().connect() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        response.delete_cookie("trendforge_session")

    @app.get("/api/v1/settings")
    def settings_get(request: Request):
        operator(request)
        settings = app.state.settings.public()
        settings["ffmpeg_available"] = bool(Path(ffmpeg()).is_file())
        settings["speech_models_ready"] = [m for m in ("tiny", "base", "small") if (directory / "models" / f".ready-{m}").exists()]
        settings["active_job"] = public(db().active_job())
        return settings

    @app.patch("/api/v1/settings")
    def settings_patch(request: Request, body: dict = Body(...)):
        operator(request)
        allowed = {"ai_base_url", "ai_model", "ai_api_key", "youtube_api_key", "pexels_api_key", "speech_model"}
        if set(body) - allowed or any(not isinstance(v, str) or len(v) > 2000 for v in body.values()):
            raise AppError("Check the connection settings.")
        if body.get("ai_base_url"):
            body["ai_base_url"] = validate_base_url(body["ai_base_url"].strip())
        if "speech_model" in body and body["speech_model"] not in {"tiny", "base", "small"}:
            raise AppError("Choose a supported multilingual speech model.")
        # An omitted credential is preserved; an explicit empty string removes it.
        app.state.settings.update({k: v.strip() for k, v in body.items()})
        return app.state.settings.public()

    @app.post("/api/v1/settings/test")
    async def settings_test(request: Request, body: dict = Body(...)):
        operator(request)
        if body.get("provider") == "ai":
            await provider_json(app.state.settings, 'Return {"connected":true}.', {"connection_test": True})
            return {"ok": True, "message": "Your AI provider is connected."}
        if body.get("provider") == "youtube":
            from .integrations import youtube_get
            key = app.state.settings.get("youtube_api_key")
            if not key:
                raise AppError("Save a YouTube API key first.")
            async with httpx.AsyncClient(timeout=20) as client:
                await youtube_get(client, "i18nRegions", {"part": "snippet", "hl": "en"}, key)
            return {"ok": True, "message": "YouTube Data API is connected."}
        raise AppError("Choose AI or YouTube to test.")

    @app.get("/api/v1/settings/connector")
    def connector_config(request: Request):
        operator(request)
        return {"mcpServers": {"trendforge": {"type": "stdio", "command": str(Path(os.sys.executable)),
            "args": ["-m", "trendforge.mcp_server"],
            "env": {"TRENDFORGE_DATA_DIR": str(directory), "TRENDFORGE_URL": str(request.base_url).rstrip("/")}}}}

    @app.post("/api/v1/settings/speech-model", status_code=202)
    def download_model(request: Request):
        operator(request)
        return launch("__system", "model_download", {"model": app.state.settings.get("speech_model")}, request)

    @app.get("/api/v1/jobs/{jid}")
    def global_job(jid: str):
        return public(db().job(jid))

    @app.post("/api/v1/jobs/{jid}/cancel")
    def global_cancel(jid: str):
        return public(app.state.worker.cancel(jid))

    @app.get("/api/v1/projects")
    def projects():
        return [{**p, "asset_count": len(db().docs(p["id"], "asset")), "export_count": len(valid_exports(p["id"]))} for p in db().projects()]

    @app.post("/api/v1/projects", status_code=201)
    def create_project(body: ProjectInput):
        return db().create_project(body.model_dump())

    @app.get("/api/v1/projects/{pid}")
    def project_get(pid: str):
        return hydrate(pid)

    @app.patch("/api/v1/projects/{pid}")
    def project_patch(pid: str, body: dict = Body(...)):
        expected = body.pop("expected_project_revision", None)
        with db().lock:
            p = db().assert_editable(pid, expected)
            try:
                updated = ProjectInput.model_validate({**{k: p[k] for k in ProjectInput.model_fields}, **body}).model_dump()
            except ValidationError:
                raise AppError("Check your project details.")
            db().update_project(pid, {**updated, **invalidate(pid, "brief"), "brief_id": None, "ideas": [], "phase": "CONTEXT_READY"}, expected)
        return hydrate(pid)

    @app.delete("/api/v1/projects/{pid}", status_code=204)
    def project_delete(pid: str, request: Request, body: dict = Body(...)):
        operator(request)
        if body.get("confirmation") is not True:
            raise AppError("Confirm that you want to delete this project.")
        with db().lock:
            db().assert_editable(pid, body.get("expected_project_revision"))
            paths = [directory / "projects" / pid]
            with db().connect() as c:
                paths += [directory / "jobs" / row["id"] for row in c.execute("SELECT id FROM jobs WHERE project_id=?", (pid,))]
            try:
                for path in paths:
                    if not path.resolve().is_relative_to(directory):
                        raise OSError("Invalid project path")
                    if path.exists():
                        shutil.rmtree(path)
            except OSError:
                raise AppError("Some project files are in use. Close their previews and try deleting again. The project has not been marked deleted.", "DELETION_FAILED", 409)
            db().delete_project(pid)

    @app.get("/api/v1/projects/{pid}/research")
    def research_list(pid: str):
        db().project(pid)
        return db().docs(pid, "research")

    async def perform_research(pid: str, body: ResearchInput):
        p = db().assert_editable(pid)
        matching = [r for r in db().docs(pid, "research") if all(r.get(k) == v for k, v in body.model_dump().items()) and r.get("data_mode") != "manual"]
        if matching and datetime.fromisoformat(matching[-1]["fetched_at"]) > datetime.now(timezone.utc) - timedelta(hours=1):
            return {**matching[-1], "data_mode": "cache"}
        cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        count = sum(1 for project in db().projects() for r in db().docs(project["id"], "research") if r.get("data_mode") == "live" and r.get("fetched_at", "") > cutoff)
        if count >= 20 and body.source_mode != "manual":
            raise AppError("The local research budget is 20 live searches per 24 hours. Use saved research or continue without research.", "RESEARCH_LIMIT", 429)
        result = await research_youtube(app.state.settings, body)
        with db().lock:
            db().assert_editable(pid, p["revision"])
            run = db().add_doc(pid, "research", result)
            changes = {"research_id": run["id"]}
            if p["phase"] in {"CONTEXT_READY", "RESEARCH_READY"}:
                changes["phase"] = "RESEARCH_READY"
            db().update_project(pid, changes, p["revision"])
        return run

    @app.post("/api/v1/projects/{pid}/research")
    async def research(pid: str, body: ResearchInput):
        async with app.state.research_lock:
            return await perform_research(pid, body)

    def selected_sources(pid, ids):
        if not isinstance(ids, list) or len(ids) > 20 or any(not isinstance(x, str) for x in ids):
            raise AppError("Choose valid research references.")
        known = {x["video_id"]: x for r in db().docs(pid, "research") for x in r.get("items", [])}
        if any(x not in known for x in ids):
            raise AppError("One of the selected references is no longer available. Refresh your research.")
        return [known[x] for x in dict.fromkeys(ids)]

    @app.post("/api/v1/projects/{pid}/ai/ideas")
    async def ai_ideas(pid: str, body: dict = Body(...)):
        p = db().assert_editable(pid, body.get("expected_project_revision"))
        sources = selected_sources(pid, body.get("source_video_ids", []))
        ideas = await generate_ideas(app.state.settings, p, sources)
        with db().lock:
            db().assert_editable(pid, p["revision"])
            db().update_project(pid, {"ideas": ideas, "idea_source_video_ids": [x["video_id"] for x in sources]}, p["revision"])
        db().event(pid, "ideas_generated")
        return {"ideas": ideas, "label": "AI suggestions"}

    @app.post("/api/v1/projects/{pid}/ai/brief")
    async def ai_brief(pid: str, body: dict = Body(...)):
        p = db().assert_editable(pid, body.get("expected_project_revision"))
        idea = next((x for x in p.get("ideas", []) if x["id"] == body.get("idea_id")), None)
        if not idea:
            raise AppError("Choose one of your generated ideas first.")
        sources = selected_sources(pid, p.get("idea_source_video_ids", []))
        brief = await generate_brief(app.state.settings, p, idea, sources)
        return save_brief(pid, brief)

    @app.post("/api/v1/projects/{pid}/briefs", status_code=201)
    def brief_post(pid: str, body: BriefInput):
        return save_brief(pid, body)

    @app.get("/api/v1/projects/{pid}/briefs/{did}")
    def brief_get(pid: str, did: str):
        return public(db().doc(pid, did, "brief"))

    @app.post("/api/v1/projects/{pid}/briefs/{did}/approve")
    def brief_approve(pid: str, did: str, request: Request, body: Approval):
        operator(request)
        with db().lock:
            p = db().assert_editable(pid, body.expected_project_revision)
            if p["brief_id"] != did:
                raise AppError("Review the current brief before approving.", "STALE_BRIEF", 409)
            brief = db().update_doc(pid, did, {"status": "approved", "approved_at": now()})
            db().update_project(pid, {"phase": "BRIEF_APPROVED"}, p["revision"])
            db().event(pid, "brief_approved", {"brief_id": did})
        return public(brief)

    async def ingest(pid, file, filename, rights=True, provenance=None):
        if not rights:
            raise AppError("Confirm that you have the right to use these clips.", "RIGHTS_REQUIRED")
        with db().lock:
            p = db().assert_editable(pid)
            if not p.get("brief_id") or db().doc(pid, p["brief_id"], "brief")["status"] != "approved":
                raise AppError("Approve your brief before uploading footage.", "APPROVAL_REQUIRED", 409)
            if len(db().docs(pid, "asset")) >= 5:
                raise AppError("A project can contain up to five clips.", "CLIP_LIMIT")
        folder = directory / "projects" / pid / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / (new_id("file") + Path(filename).suffix.lower())
        size, digest = 0, hashlib.sha256()
        try:
            with destination.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_FILE:
                        raise AppError("This file is larger than 100 MiB.", "FILE_TOO_LARGE", 413)
                    output.write(chunk)
                    digest.update(chunk)
            metadata = await asyncio.to_thread(validate_upload, destination, filename)
            with db().lock:
                p = db().assert_editable(pid)
                assets = db().docs(pid, "asset")
                if len(assets) >= 5 or sum(x["bytes"] for x in assets) + size > MAX_TOTAL:
                    raise AppError("Use at most five clips and 500 MiB per project.", "PROJECT_LIMIT")
                if sum(x["duration_seconds"] for x in assets) + metadata["duration_seconds"] > 600.1:
                    raise AppError("Keep the total footage duration at or below ten minutes.", "DURATION_LIMIT")
                asset = db().add_doc(pid, "asset", {**metadata, "original_name": Path(filename).name[:160],
                    "bytes": size, "sha256": digest.hexdigest(), "file_ref": str(destination.relative_to(directory)),
                    "rights_confirmed_at": now(), "source": "pexels" if provenance else "upload", "provenance": provenance,
                    "validation_status": "valid"})
                db().update_project(pid, {**invalidate(pid, "asset"), "phase": "ASSETS_READY" if len(assets) + 1 >= 3 else "BRIEF_APPROVED"}, p["revision"])
            db().event(pid, "asset_uploaded", {"asset_id": asset["id"]})
            return public(asset)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

    @app.post("/api/v1/projects/{pid}/assets", status_code=201)
    async def asset_upload(pid: str, file: UploadFile = File(...), rights_confirmed: bool = Form(False)):
        return await ingest(pid, file, file.filename or "clip.mp4", rights_confirmed)

    @app.get("/api/v1/projects/{pid}/assets")
    def asset_list(pid: str):
        db().project(pid)
        return public(db().docs(pid, "asset"))

    @app.get("/api/v1/projects/{pid}/assets/{aid}/media")
    def asset_media(pid: str, aid: str):
        asset = db().doc(pid, aid, "asset")
        return FileResponse(safe_path(asset["file_ref"]), media_type="video/mp4")

    @app.delete("/api/v1/projects/{pid}/assets/{aid}", status_code=204)
    def asset_delete(pid: str, aid: str, request: Request, body: dict = Body(...)):
        operator(request)
        if body.get("confirmation") is not True:
            raise AppError("Confirm that you want to remove this clip.")
        with db().lock:
            p = db().assert_editable(pid, body.get("expected_project_revision"))
            asset = db().doc(pid, aid, "asset")
            try:
                safe_path(asset["file_ref"]).unlink()
            except OSError:
                raise AppError("This clip is in use. Close its preview and try again.", "FILE_IN_USE", 409)
            db().remove_doc(pid, aid)
            db().update_project(pid, {**invalidate(pid, "asset"), "phase": "ASSETS_READY" if len(db().docs(pid, "asset")) >= 3 else "BRIEF_APPROVED"}, p["revision"])

    @app.post("/api/v1/projects/{pid}/plans/auto", status_code=201)
    def plan_auto(pid: str, body: dict = Body(...)):
        p = db().assert_editable(pid, body.get("expected_project_revision"))
        try:
            segments = allocate_segments(db().docs(pid, "asset"), p["target_duration_seconds"])
        except ValueError as exc:
            raise AppError(str(exc), "INSUFFICIENT_FOOTAGE")
        return save_plan(pid, PlanInput(brief_revision_id=p["brief_id"], target_duration_seconds=p["target_duration_seconds"],
            segments=segments, expected_project_revision=p["revision"]))

    @app.post("/api/v1/projects/{pid}/plans", status_code=201)
    def plan_post(pid: str, body: PlanInput):
        return save_plan(pid, body)

    @app.get("/api/v1/projects/{pid}/plans/{did}")
    def plan_get(pid: str, did: str):
        return public(db().doc(pid, did, "plan"))

    @app.post("/api/v1/projects/{pid}/plans/{did}/approve")
    def plan_approve(pid: str, did: str, request: Request, body: Approval):
        operator(request)
        with db().lock:
            p = db().assert_editable(pid, body.expected_project_revision)
            if did != p["plan_id"]:
                raise AppError("Review the current plan before approving.", "STALE_PLAN", 409)
            plan = db().update_doc(pid, did, {"status": "approved", "approved_at": now()})
            db().update_project(pid, {"phase": "PLAN_APPROVED"}, p["revision"])
        return public(plan)

    @app.post("/api/v1/projects/{pid}/prepare-jobs", status_code=202)
    def prepare(pid: str, request: Request, body: dict = Body(...)):
        with db().lock:
            p = db().project(pid)
            plan = db().doc(pid, body.get("plan_id") or p.get("plan_id"), "plan")
            if plan["id"] != p["plan_id"] or plan["status"] != "approved":
                raise AppError("Approve the current edit plan first.", "APPROVAL_REQUIRED", 409)
            return launch(pid, "prepare", {"plan_id": plan["id"], "speech_model": app.state.settings.get("speech_model")}, request)

    @app.get("/api/v1/projects/{pid}/drafts/{did}")
    def draft_get(pid: str, did: str):
        return public(db().doc(pid, did, "draft"))

    @app.get("/api/v1/projects/{pid}/drafts/{did}/media")
    def draft_media(pid: str, did: str):
        return FileResponse(safe_path(db().doc(pid, did, "draft")["file_ref"]), media_type="video/mp4")

    @app.post("/api/v1/projects/{pid}/transcription-jobs", status_code=202)
    def transcribe(pid: str, request: Request, body: dict = Body(...)):
        p = db().project(pid)
        did = body.get("draft_id") or p.get("draft_id")
        if did != p.get("draft_id") or not did:
            raise AppError("Create a current video draft before transcribing.", "DRAFT_REQUIRED", 409)
        db().doc(pid, did, "draft")
        return launch(pid, "transcribe", {"draft_id": did, "speech_model": app.state.settings.get("speech_model")}, request)

    @app.get("/api/v1/projects/{pid}/subtitles/{did}")
    def subtitles_get(pid: str, did: str):
        return public(db().doc(pid, did, "subtitle"))

    @app.post("/api/v1/projects/{pid}/subtitles", status_code=201)
    def subtitles_post(pid: str, body: SubtitleInput):
        with db().lock:
            p = db().assert_editable(pid, body.expected_project_revision)
            if body.draft_id != p.get("draft_id"):
                raise AppError("These subtitles belong to an older video. Open the current draft.", "STALE_TIMELINE", 409)
            draft = db().doc(pid, body.draft_id, "draft")
            cues = [x.model_dump() for x in body.cues]
            try:
                validate_cues(cues, draft["duration_seconds"], body.speech_status == "no_speech")
            except ValueError as exc:
                raise AppError(str(exc), "INVALID_SUBTITLES")
            track = db().add_doc(pid, "subtitle", {"draft_id": draft["id"], "cues": cues,
                "speech_status": body.speech_status, "source": "manual", "language": "id", "status": "draft"})
            db().update_project(pid, {"subtitle_id": track["id"], "export_id": None, "ready_confirmed_at": None, "phase": "CAPTIONS_REVIEW"}, p["revision"])
        return public(track)

    @app.post("/api/v1/projects/{pid}/subtitles/{did}/approve")
    def subtitles_approve(pid: str, did: str, request: Request, body: Approval):
        operator(request)
        with db().lock:
            p = db().assert_editable(pid, body.expected_project_revision)
            if did != p["subtitle_id"]:
                raise AppError("Review the current subtitles before approving.", "STALE_SUBTITLES", 409)
            track = db().doc(pid, did, "subtitle")
            if track["draft_id"] != p["draft_id"]:
                raise AppError("The video timeline changed. Review the new subtitles.", "STALE_TIMELINE", 409)
            if track["speech_status"] == "no_speech" and not body.no_speech_decision:
                raise AppError("Confirm that you want to continue without subtitles.", "NO_SPEECH_CONFIRMATION")
            track = db().update_doc(pid, did, {"status": "approved", "approved_at": now(),
                "no_speech_confirmed_at": now() if body.no_speech_decision else None})
            db().update_project(pid, {"phase": "READY_TO_EXPORT"}, p["revision"])
            return public(track)

    @app.post("/api/v1/projects/{pid}/export-jobs", status_code=202)
    def export_start(pid: str, request: Request, body: dict = Body(...)):
        with db().lock:
            p = db().project(pid)
            if not p.get("draft_id") or not p.get("subtitle_id"):
                raise AppError("Prepare your video and review the subtitles first.", "REVIEW_REQUIRED", 409)
            track = db().doc(pid, p["subtitle_id"], "subtitle")
            draft = db().doc(pid, p["draft_id"], "draft")
            if track["status"] != "approved" or track["draft_id"] != draft["id"] or draft["plan_id"] != p["plan_id"]:
                raise AppError("Approve the subtitles for the current video before exporting.", "APPROVAL_REQUIRED", 409)
            return launch(pid, "export", {"draft_id": draft["id"], "subtitle_id": track["id"], "large_text": bool(body.get("large_text", False))}, request)

    @app.get("/api/v1/projects/{pid}/jobs/{jid}")
    def job_get(pid: str, jid: str):
        return public(db().job(jid, pid))

    @app.post("/api/v1/projects/{pid}/jobs/{jid}/cancel")
    def job_cancel(pid: str, jid: str):
        db().job(jid, pid)
        return public(app.state.worker.cancel(jid))

    @app.get("/api/v1/projects/{pid}/exports")
    def exports(pid: str):
        return public(valid_exports(pid))

    @app.get("/api/v1/projects/{pid}/exports/{eid}/files/{kind}")
    def export_file(pid: str, eid: str, kind: str, download: bool = False):
        if kind not in {"mp4", "srt"}:
            raise AppError("Choose MP4 or SRT.", "NOT_FOUND", 404)
        export = db().doc(pid, eid, "export")
        if db().job(export["job_id"])["status"] != "succeeded" or not export.get(kind + "_ref"):
            raise AppError("This file is not available.", "FILE_NOT_FOUND", 404)
        path = safe_path(export[kind + "_ref"])
        project = db().project(pid)
        filename = re.sub(r"[^A-Za-z0-9_-]", "-", project["niche"])[:60] + "-" + eid[-6:] + "." + kind
        return FileResponse(path, media_type="video/mp4" if kind == "mp4" else "application/x-subrip",
            filename=filename if download else None,
            background=BackgroundTask(db().event, pid, "download_completed", {"export_id": eid, "kind": kind}) if download else None)

    @app.post("/api/v1/projects/{pid}/ready-confirmation")
    def ready_confirm(pid: str, request: Request, body: dict = Body(...)):
        operator(request)
        p = db().project(pid)
        eid = body.get("export_id")
        if body.get("confirmation") is not True or not eid or eid != p.get("export_id"):
            raise AppError("Review the current exported video before confirming.")
        if not any(x["name"] == "download_completed" and json.loads(x["data"]).get("export_id") == eid and json.loads(x["data"]).get("kind") == "mp4" for x in db().events(pid)):
            raise AppError("Download your MP4 before marking it ready to upload.", "DOWNLOAD_REQUIRED")
        if not p.get("ready_confirmed_at"):
            db().update_project(pid, {"ready_confirmed_at": now(), "phase": "USER_CONFIRMED_READY"})
            db().event(pid, "ready_confirmed", {"export_id": eid})
        return hydrate(pid)

    @app.get("/api/v1/stock/search")
    async def stock_search(query: str):
        if not 2 <= len(query) <= 100:
            raise AppError("Enter a search between 2 and 100 characters.")
        return await pexels_search(app.state.settings, query)

    @app.post("/api/v1/projects/{pid}/stock/import", status_code=201)
    async def stock_import(pid: str, body: dict = Body(...)):
        results = await pexels_search(app.state.settings, str(body.get("query", ""))[:100])
        stock = next((v for v in results if v["id"] == body.get("video_id")), None)
        if not stock:
            raise AppError("This stock clip is no longer in the search results.")
        url = stock["file_url"]
        parsed = urlparse(url)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".pexels.com"):
            raise AppError("The stock file is not hosted on an approved media domain.")
        import tempfile
        with tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024) as temp:
            try:
                async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
                    async with client.stream("GET", url) as response:
                        if response.status_code != 200:
                            raise AppError("The stock file could not be downloaded. Use your own footage or try another clip.")
                        size = 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > MAX_FILE:
                                raise AppError("This stock clip is larger than 100 MiB.", "FILE_TOO_LARGE", 413)
                            temp.write(chunk)
                temp.seek(0)
                upload = UploadFile(file=temp, filename=f"pexels-{stock['id']}.mp4")
                return await ingest(pid, upload, upload.filename, True, {k: stock[k] for k in ("id", "url", "creator", "creator_url")})
            except httpx.HTTPError:
                raise AppError("The stock download was interrupted. Your uploaded clips are safe.", "STOCK_DOWNLOAD_FAILED", 503)

    app.mount("/static", StaticFiles(directory=STATIC, check_dir=False), name="static")

    @app.get("/")
    @app.get("/projects/{path:path}")
    @app.get("/connections")
    @app.get("/exports")
    def index():
        return FileResponse(STATIC / "index.html")

    return app


app = create_app()
