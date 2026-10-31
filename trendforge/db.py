import hashlib
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import libsql

from . import config  # Load the project .env for direct database clients too.
from .errors import AppError


class RemoteCursor:
    """Keep sqlite3.Row-style named access for the official libSQL driver."""

    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(zip((c[0] for c in self.cursor.description), row)) if row is not None else None

    def fetchall(self):
        return list(self)

    def __iter__(self):
        while (row := self.fetchone()) is not None:
            yield row


class RemoteConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, parameters=()):
        return RemoteCursor(self.connection.execute(sql, parameters))

    def executescript(self, sql):
        return self.connection.executescript(sql)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


class Database:
    def __init__(self, path, *, backend=None, url=None, token=None):
        self.path = str(path)
        self.url = (url if url is not None else os.getenv("TURSO_DATABASE_URL", "")).strip()
        self.token = (token if token is not None else os.getenv("TURSO_AUTH_TOKEN", "")).strip()
        self.backend = backend or os.getenv("TRENDFORGE_DATABASE_BACKEND") or ("turso" if self.url or self.token else "sqlite")
        if self.backend not in {"sqlite", "turso"}:
            raise AppError("Choose sqlite or turso as the database backend.", "DATABASE_CONFIG", 503)
        if self.backend == "turso":
            parsed = urlparse(self.url)
            try:
                port_ok = parsed.port in (None, 443)
            except ValueError:
                port_ok = False
            if (not self.token or parsed.scheme not in {"libsql", "https"} or not parsed.hostname
                    or not parsed.hostname.endswith(".turso.io") or parsed.username or parsed.password
                    or not port_ok or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
                raise AppError("Set a valid Turso database URL and auth token in the environment.", "DATABASE_CONFIG", 503)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.context = threading.local()
        with self.connect() as c:
            if self.backend == "sqlite":
                c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    kind TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS docs_project ON documents(project_id,kind);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    status TEXT NOT NULL, data TEXT NOT NULL, idem_key TEXT UNIQUE, payload_hash TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs((1))
                    WHERE status IN ('queued','running','cancelling');
                CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    name TEXT NOT NULL, time TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,
                    expires REAL NOT NULL, csrf TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        with self.lock:
            # Nested methods participate in the caller's transaction. Opening a
            # second remote connection here could deadlock on the first writer.
            if getattr(self.context, "connection", None) is not None:
                yield self.context.connection
                return
            c = None
            try:
                if self.backend == "turso":
                    c = RemoteConnection(libsql.connect(self.url, auth_token=self.token, timeout=20))
                else:
                    c = sqlite3.connect(self.path, timeout=20)
                    c.row_factory = sqlite3.Row
                self.context.connection = c
                yield c
                c.commit()
            except libsql.Error:
                if c:
                    try:
                        c.rollback()
                    except libsql.Error:
                        pass
                raise AppError("The Turso database operation failed. Check the connection and database credentials.", "DATABASE_UNAVAILABLE", 503) from None
            except Exception:
                if c:
                    c.rollback()
                raise
            finally:
                self.context.connection = None
                if c:
                    c.close()

    def create_project(self, fields):
        p = {**fields, "id": new_id("prj"), "revision": 1, "phase": "CONTEXT_READY",
             "created_at": now(), "updated_at": now(), "task_started_at": now(),
             "brief_id": None, "plan_id": None, "draft_id": None,
             "subtitle_id": None, "export_id": None, "ideas": [], "ready_confirmed_at": None}
        with self.connect() as c:
            c.execute("INSERT INTO projects VALUES (?,?)", (p["id"], json.dumps(p)))
        self.event(p["id"], "task_started")
        return p

    def project(self, pid):
        with self.connect() as c:
            row = c.execute("SELECT data FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            raise AppError("This project was not found.", "NOT_FOUND", 404)
        return json.loads(row["data"])

    def projects(self):
        with self.connect() as c:
            rows = c.execute("SELECT data FROM projects ORDER BY rowid DESC").fetchall()
        return [json.loads(r["data"]) for r in rows]

    def update_project(self, pid, changes, expected=None):
        with self.connect() as c:
            p = self.project(pid)
            if expected is not None and p["revision"] != expected:
                raise AppError("This project changed. Refresh before saving.", "STALE_REVISION", 409,
                               {"revision": p["revision"]})
            p.update(changes)
            p["revision"] += 1
            p["updated_at"] = now()
            c.execute("UPDATE projects SET data=? WHERE id=?", (json.dumps(p), pid))
        return p

    def add_doc(self, pid, kind, data):
        self.project(pid)
        d = {**data, "id": new_id(kind), "project_id": pid, "created_at": now()}
        with self.connect() as c:
            c.execute("INSERT INTO documents VALUES (?,?,?,?,?)",
                      (d["id"], pid, kind, json.dumps(d), d["created_at"]))
        return d

    def doc(self, pid, did, kind=None):
        with self.connect() as c:
            row = c.execute("SELECT * FROM documents WHERE id=? AND project_id=?", (did, pid)).fetchone()
        if not row or (kind and row["kind"] != kind):
            raise AppError("This item was not found in the project.", "NOT_FOUND", 404)
        return json.loads(row["data"])

    def docs(self, pid, kind):
        with self.connect() as c:
            rows = c.execute("SELECT data FROM documents WHERE project_id=? AND kind=? ORDER BY rowid",
                             (pid, kind)).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def update_doc(self, pid, did, changes):
        d = self.doc(pid, did)
        d.update(changes)
        with self.connect() as c:
            c.execute("UPDATE documents SET data=? WHERE id=? AND project_id=?", (json.dumps(d), did, pid))
        return d

    def remove_doc(self, pid, did):
        with self.connect() as c:
            c.execute("DELETE FROM documents WHERE id=? AND project_id=?", (did, pid))

    def event(self, pid, name, properties=None):
        with self.connect() as c:
            c.execute("INSERT INTO events VALUES (?,?,?,?,?)",
                      (new_id("evt"), pid, name, now(), json.dumps(properties or {})))

    def events(self, pid):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT name,time,data FROM events WHERE project_id=? ORDER BY rowid", (pid,))]

    def active_job(self, pid=None):
        with self.connect() as c:
            query = "SELECT data FROM jobs WHERE status IN ('queued','running','cancelling')"
            row = c.execute(query + (" AND project_id=?" if pid else ""), (pid,) if pid else ()).fetchone()
        return json.loads(row["data"]) if row else None

    def assert_editable(self, pid, expected=None):
        p = self.project(pid)
        if self.active_job(pid):
            raise AppError("Cancel or finish the current job before making changes.", "JOB_ACTIVE", 409)
        if expected is not None and expected != p["revision"]:
            raise AppError("This project changed. Refresh before saving.", "STALE_REVISION", 409)
        return p

    def start_job(self, pid, kind, snapshot, key):
        # Provider/model configuration is snapshotted for execution, but is not part of the caller's repeated request body.
        request_input = {k: v for k, v in snapshot.items() if k != "speech_model"}
        payload_hash = hashlib.sha256(json.dumps({"project": pid, "kind": kind, "input": request_input}, sort_keys=True).encode()).hexdigest()
        with self.connect() as c:
            prior = c.execute("SELECT data,payload_hash FROM jobs WHERE idem_key=?", (key,)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash:
                    raise AppError("This request key was already used for a different operation.", "IDEMPOTENCY_CONFLICT", 409)
                return json.loads(prior["data"]), False
            if self.active_job():
                raise AppError("Another video or speech model is being processed. Wait or cancel it first.", "WORKER_BUSY", 409)
            j = {"id": new_id("job"), "project_id": pid, "type": kind, "status": "queued",
                 "stage": "Waiting to start", "progress_percent": 0, "input": snapshot,
                 "created_at": now(), "started_at": None, "finished_at": None,
                 "output": {}, "error": None}
            c.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?)", (j["id"], pid, "queued", json.dumps(j), key, payload_hash))
        self.event(pid, "job_queued", {"job_id": j["id"], "type": kind})
        return j, True

    def job(self, jid, pid=None):
        with self.connect() as c:
            row = c.execute("SELECT data FROM jobs WHERE id=?", (jid,)).fetchone()
        if not row:
            raise AppError("This job was not found.", "NOT_FOUND", 404)
        j = json.loads(row["data"])
        if pid and j["project_id"] != pid:
            raise AppError("This job was not found.", "NOT_FOUND", 404)
        return j

    def update_job(self, jid, changes):
        with self.connect() as c:
            j = self.job(jid)
            j.update(changes)
            c.execute("UPDATE jobs SET status=?,data=? WHERE id=?", (j["status"], json.dumps(j), jid))
        return j

    def interrupt_jobs(self):
        with self.connect() as c:
            rows = c.execute("SELECT id FROM jobs WHERE status IN ('queued','running','cancelling')").fetchall()
            for row in rows:
                self.update_job(row["id"], {"status": "failed", "stage": "Interrupted",
                    "finished_at": now(), "error": {"code": "INTERRUPTED", "message": "The service stopped. Your saved inputs are safe; start this step again."}})

    def delete_project(self, pid):
        with self.connect() as c:
            for table in ("documents", "jobs", "events"):
                c.execute(f"DELETE FROM {table} WHERE project_id=?", (pid,))
            c.execute("DELETE FROM projects WHERE id=?", (pid,))

