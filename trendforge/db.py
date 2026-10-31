import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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


def invalidation(level):
    """Project fields to clear when an upstream input changes (shared by the API and the worker)."""
    changes = {"export_id": None, "ready_confirmed_at": None}
    if level in {"brief", "asset"}:
        changes.update({"plan_id": None, "draft_id": None, "subtitle_id": None})
    elif level == "plan":
        changes.update({"draft_id": None, "subtitle_id": None})
    return changes


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
                CREATE TABLE IF NOT EXISTS workers(id TEXT PRIMARY KEY, last_seen REAL NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    name TEXT NOT NULL, time TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,
                    expires REAL NOT NULL, csrf TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL, password_hash TEXT NOT NULL, password_salt TEXT NOT NULL,
                    created_at TEXT NOT NULL, disabled_at TEXT);
                CREATE TABLE IF NOT EXISTS api_tokens(id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE, label TEXT NOT NULL, created_at TEXT NOT NULL,
                    last_used_at TEXT, revoked_at TEXT);
                CREATE TABLE IF NOT EXISTS login_failures(id TEXT PRIMARY KEY, scope TEXT NOT NULL, time REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS login_failures_scope ON login_failures(scope,time);
            """)
            # Columns added for accounts. Existing workspaces are upgraded in place.
            self._add_column(c, "projects", "owner_id", "TEXT")
            self._add_column(c, "sessions", "user_id", "TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS projects_owner ON projects(owner_id)")
            # Single-password sessions from before accounts belong to nobody.
            c.execute("DELETE FROM sessions WHERE user_id IS NULL")
            # Job queue: a worker (embedded or separate) claims jobs and holds a renewable lease.
            self._add_column(c, "jobs", "lane", "TEXT")
            self._add_column(c, "jobs", "lease_until", "REAL")
            self._add_column(c, "jobs", "worker_id", "TEXT")
            # One active video job per project; other projects queue instead of being refused.
            c.execute("DROP INDEX IF EXISTS one_active_job")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_active_media_job ON jobs(project_id) "
                      "WHERE status IN ('queued','running','cancelling') AND lane='media'")
            c.execute("CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(lane,status)")

    @staticmethod
    def _add_column(c, table, column, kind):
        if column not in {row["name"] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")

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

    def create_project(self, fields, owner_id=None):
        p = {**fields, "id": new_id("prj"), "revision": 1, "phase": "CONTEXT_READY",
             "created_at": now(), "updated_at": now(), "task_started_at": now(),
             "brief_id": None, "plan_id": None, "draft_id": None,
             "subtitle_id": None, "export_id": None, "ideas": [], "ready_confirmed_at": None}
        with self.connect() as c:
            c.execute("INSERT INTO projects(id,data,owner_id) VALUES (?,?,?)", (p["id"], json.dumps(p), owner_id))
        self.event(p["id"], "task_started")
        return p

    def project_owner(self, pid):
        with self.connect() as c:
            row = c.execute("SELECT owner_id FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            raise AppError("This project was not found.", "NOT_FOUND", 404)
        return row["owner_id"]

    def claim_projects(self, user_id):
        """Give projects created before accounts existed to one user."""
        with self.connect() as c:
            ids = [r["id"] for r in c.execute("SELECT id FROM projects WHERE owner_id IS NULL").fetchall()]
            c.execute("UPDATE projects SET owner_id=? WHERE owner_id IS NULL", (user_id,))
        return ids

    # Accounts -----------------------------------------------------------------

    def create_user(self, username, display_name, password_hash, password_salt):
        user = {"id": new_id("usr"), "username": username, "display_name": display_name, "created_at": now()}
        with self.connect() as c:
            if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                raise AppError("This username is already taken. Choose another one.", "USERNAME_TAKEN", 409)
            c.execute("INSERT INTO users(id,username,display_name,password_hash,password_salt,created_at) VALUES (?,?,?,?,?,?)",
                      (user["id"], username, display_name, password_hash, password_salt, user["created_at"]))
        return user

    def user_by_username(self, username):
        with self.connect() as c:
            row = c.execute("SELECT * FROM users WHERE username=? AND disabled_at IS NULL", (username,)).fetchone()
        return dict(row) if row else None

    def user(self, user_id):
        with self.connect() as c:
            row = c.execute("SELECT * FROM users WHERE id=? AND disabled_at IS NULL", (user_id,)).fetchone()
        return dict(row) if row else None

    def set_password(self, user_id, password_hash, password_salt, keep_session_hash=None):
        """Change a password and sign out every other session of that user."""
        with self.connect() as c:
            c.execute("UPDATE users SET password_hash=?, password_salt=? WHERE id=?", (password_hash, password_salt, user_id))
            c.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user_id, keep_session_hash or ""))

    def create_session(self, token_hash, user_id, expires, csrf):
        with self.connect() as c:
            c.execute("INSERT INTO sessions(token_hash,expires,csrf,user_id) VALUES (?,?,?,?)", (token_hash, expires, csrf, user_id))

    def session_user(self, token_hash, at):
        with self.connect() as c:
            row = c.execute("SELECT s.csrf, u.id, u.username, u.display_name FROM sessions s JOIN users u ON u.id=s.user_id "
                            "WHERE s.token_hash=? AND s.expires>? AND u.disabled_at IS NULL", (token_hash, at)).fetchone()
        return dict(row) if row else None

    def delete_session(self, token_hash):
        with self.connect() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def create_token(self, user_id, label, token_hash):
        token = {"id": new_id("tok"), "label": label, "created_at": now(), "last_used_at": None}
        with self.connect() as c:
            c.execute("INSERT INTO api_tokens(id,user_id,token_hash,label,created_at) VALUES (?,?,?,?,?)",
                      (token["id"], user_id, token_hash, label, token["created_at"]))
        return token

    def token_user(self, token_hash):
        with self.connect() as c:
            row = c.execute("SELECT t.id AS token_id, t.last_used_at, u.id, u.username, u.display_name FROM api_tokens t "
                            "JOIN users u ON u.id=t.user_id WHERE t.token_hash=? AND t.revoked_at IS NULL "
                            "AND u.disabled_at IS NULL", (token_hash,)).fetchone()
            if row and (row["last_used_at"] or "") < (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat():
                c.execute("UPDATE api_tokens SET last_used_at=? WHERE id=?", (now(), row["token_id"]))
        return dict(row) if row else None

    def tokens(self, user_id):
        with self.connect() as c:
            rows = c.execute("SELECT id,label,created_at,last_used_at FROM api_tokens WHERE user_id=? AND revoked_at IS NULL "
                             "ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def revoke_token(self, user_id, token_id):
        with self.connect() as c:
            row = c.execute("SELECT id FROM api_tokens WHERE id=? AND user_id=? AND revoked_at IS NULL", (token_id, user_id)).fetchone()
            if not row:
                raise AppError("This connector token was not found.", "NOT_FOUND", 404)
            c.execute("UPDATE api_tokens SET revoked_at=? WHERE id=?", (now(), token_id))

    def record_failure(self, scope):
        with self.connect() as c:
            c.execute("INSERT INTO login_failures VALUES (?,?,?)", (new_id("lf"), scope, time.time()))

    def recent_failures(self, scope, seconds):
        with self.connect() as c:
            return c.execute("SELECT COUNT(*) AS n FROM login_failures WHERE scope=? AND time>?",
                             (scope, time.time() - seconds)).fetchone()["n"]

    def clear_failures(self, scope):
        with self.connect() as c:
            c.execute("DELETE FROM login_failures WHERE scope=?", (scope,))

    def project(self, pid):
        with self.connect() as c:
            row = c.execute("SELECT data FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            raise AppError("This project was not found.", "NOT_FOUND", 404)
        return json.loads(row["data"])

    def projects(self, owner_id=None):
        """All projects, or only one user's projects when owner_id is given."""
        with self.connect() as c:
            if owner_id is None:
                rows = c.execute("SELECT data FROM projects ORDER BY rowid DESC").fetchall()
            else:
                rows = c.execute("SELECT data FROM projects WHERE owner_id=? ORDER BY rowid DESC", (owner_id,)).fetchall()
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

    ACTIVE = "('queued','running','cancelling')"
    INTERRUPTED = {"code": "INTERRUPTED", "message": "Processing stopped unexpectedly. Your saved inputs are safe; start this step again."}

    @staticmethod
    def lane_for(kind):
        # Upload checks are quick and must not wait behind a long render.
        return "light" if kind == "ingest" else "media"

    def active_job(self, pid=None, lane="media"):
        """The active video job (of a project, or any). Upload checks are a separate lane."""
        query = f"SELECT data FROM jobs WHERE status IN {self.ACTIVE} AND COALESCE(lane,'media')=?"
        params = [lane]
        if pid:
            query += " AND project_id=?"
            params.append(pid)
        with self.connect() as c:
            row = c.execute(query + " ORDER BY rowid LIMIT 1", tuple(params)).fetchone()
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
        lane = self.lane_for(kind)
        with self.connect() as c:
            prior = c.execute("SELECT data,payload_hash FROM jobs WHERE idem_key=?", (key,)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash:
                    raise AppError("This request key was already used for a different operation.", "IDEMPOTENCY_CONFLICT", 409)
                return json.loads(prior["data"]), False
            if lane == "media" and self.active_job(pid):
                raise AppError("This project is already processing a video. Wait or cancel it first.", "JOB_ACTIVE", 409)
            j = {"id": new_id("job"), "project_id": pid, "type": kind, "status": "queued",
                 "stage": "Waiting for the video worker", "progress_percent": 0, "input": snapshot,
                 "created_at": now(), "started_at": None, "finished_at": None,
                 "output": {}, "error": None}
            c.execute("INSERT INTO jobs(id,project_id,status,data,idem_key,payload_hash,lane) VALUES (?,?,?,?,?,?,?)",
                      (j["id"], pid, "queued", json.dumps(j), key, payload_hash, lane))
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

    # Worker queue ---------------------------------------------------------------

    def claim_job(self, lane, worker_id, lease_seconds):
        """Atomically take the oldest queued job in a lane. Safe with several workers."""
        with self.connect() as c:
            row = c.execute("UPDATE jobs SET status='running', worker_id=?, lease_until=? "
                            "WHERE id=(SELECT id FROM jobs WHERE status='queued' AND COALESCE(lane,'media')=? ORDER BY rowid LIMIT 1) "
                            "AND status='queued' RETURNING id", (worker_id, time.time() + lease_seconds, lane)).fetchone()
            if not row:
                return None
            return self.update_job(row["id"], {"status": "running", "stage": "Starting", "started_at": now()})

    def heartbeat(self, jid, worker_id, lease_seconds):
        """Extend the lease. Returns the job status, or None when this worker no longer owns it."""
        with self.connect() as c:
            row = c.execute("SELECT status FROM jobs WHERE id=? AND worker_id=?", (jid, worker_id)).fetchone()
            if not row:
                return None
            c.execute("UPDATE jobs SET lease_until=? WHERE id=? AND worker_id=?", (time.time() + lease_seconds, jid, worker_id))
            return row["status"]

    def request_cancel(self, jid):
        """Queued jobs stop at once; a running job is stopped by its worker at the next heartbeat."""
        with self.connect():
            job = self.job(jid)
            if job["status"] == "queued":
                return self.update_job(jid, {"status": "cancelled", "stage": "Cancelled", "finished_at": now()})
            if job["status"] == "running":
                return self.update_job(jid, {"status": "cancelling", "stage": "Stopping safely"})
            return job

    def recover_expired_jobs(self):
        """Jobs whose worker stopped renewing its lease are failed (or cancelled), never left running."""
        with self.connect() as c:
            rows = c.execute("SELECT id,status FROM jobs WHERE status IN ('running','cancelling') "
                             "AND (lease_until IS NULL OR lease_until<?)", (time.time(),)).fetchall()
            for row in rows:
                self._stop(row["id"], row["status"])
        return len(rows)

    def interrupt_jobs(self):
        """At start-up of the only worker: every running job belongs to a process that has died.
        Queued jobs stay queued and run next."""
        with self.connect() as c:
            for row in c.execute("SELECT id,status FROM jobs WHERE status IN ('running','cancelling')").fetchall():
                self._stop(row["id"], row["status"])

    def _stop(self, jid, status):
        if status == "cancelling":
            self.update_job(jid, {"status": "cancelled", "stage": "Cancelled", "finished_at": now()})
        else:
            self.update_job(jid, {"status": "failed", "stage": "Interrupted", "finished_at": now(), "error": self.INTERRUPTED})

    def worker_seen(self, worker_id, data):
        with self.connect() as c:
            c.execute("INSERT INTO workers(id,last_seen,data) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET "
                      "last_seen=excluded.last_seen, data=excluded.data", (worker_id, time.time(), json.dumps(data)))
            c.execute("DELETE FROM workers WHERE last_seen<?", (time.time() - 7 * 86400,))

    def workers_online(self, within_seconds=90):
        with self.connect() as c:
            rows = c.execute("SELECT id,last_seen,data FROM workers WHERE last_seen>? ORDER BY last_seen DESC",
                             (time.time() - within_seconds,)).fetchall()
        return [{"id": r["id"], "last_seen": r["last_seen"], **json.loads(r["data"])} for r in rows]

    def delete_project(self, pid):
        with self.connect() as c:
            for table in ("documents", "jobs", "events"):
                c.execute(f"DELETE FROM {table} WHERE project_id=?", (pid,))
            c.execute("DELETE FROM projects WHERE id=?", (pid,))

