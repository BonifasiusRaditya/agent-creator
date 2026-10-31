"""Backups of the database and the stored videos, and restoring them into an empty workspace.

Layout in the backup location (a folder or object storage):

    <prefix>/<snapshot-id>/database.json.gz   all application rows (no sessions or sign-in counters)
    <prefix>/<snapshot-id>/manifest.json      written last: a snapshot without it is incomplete
    <prefix>/objects/<key>                    one copy of every stored video file

Storage keys are never overwritten, so each backup only copies files that are new since the last one.
"""
import gzip
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .db import now
from .storage import MEDIA_PREFIXES

# Sessions and sign-in counters are deliberately left out: everyone signs in again after a restore.
TABLES = ("users", "api_tokens", "projects", "documents", "jobs", "events")
FILE_FIELDS = (("asset", "file_ref"), ("edited_video", "file_ref"), ("draft", "file_ref"),
               ("draft", "audio_ref"), ("export", "mp4_ref"), ("export", "srt_ref"))


class BackupError(RuntimeError):
    pass


def transfer(source, key, target, target_key):
    """Copy one object, server-side when both sides are the same store."""
    if source is target:
        source.copy(key, target_key)
        return
    with tempfile.TemporaryDirectory(prefix="trendforge-backup-") as scratch:
        target.put_file(target_key, source.fetch(key, scratch))


def snapshots(target, prefix="backups"):
    """Complete snapshot IDs, oldest first."""
    found = set()
    for key, _ in target.list(prefix):
        parts = key.split("/")
        if len(parts) == 3 and parts[2] == "manifest.json" and parts[1] != "objects":
            found.add(parts[1])
    return sorted(found)


def create_backup(db, storage, target, prefix="backups", keep=14):
    snapshot = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    tables = {}
    with db.connect() as c:
        for table in TABLES:
            columns = [row["name"] for row in c.execute(f"PRAGMA table_info({table})").fetchall()]
            rows = c.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY rowid").fetchall()
            tables[table] = {"columns": columns, "rows": [[row[col] for col in columns] for row in rows]}
    # Rows are read first: every file they reference was stored before the row was written.
    objects = sorted((key, size) for media in MEDIA_PREFIXES for key, size in storage.list(media.rstrip("/")))
    existing = dict(target.list(f"{prefix}/objects"))
    copied = 0
    for key, size in objects:
        destination = f"{prefix}/objects/{key}"
        if existing.get(destination) != size:
            transfer(storage, key, target, destination)
            copied += 1
    dump = gzip.compress(json.dumps(tables, ensure_ascii=False).encode())
    target.put_bytes(f"{prefix}/{snapshot}/database.json.gz", dump, "application/gzip")
    manifest = {"snapshot": snapshot, "created_at": now(), "database_backend": db.backend,
                "storage_backend": storage.backend, "database_sha256": hashlib.sha256(dump).hexdigest(),
                "tables": {t: len(v["rows"]) for t, v in tables.items()},
                "objects": [{"key": k, "bytes": s} for k, s in objects], "objects_copied": copied}
    target.put_bytes(f"{prefix}/{snapshot}/manifest.json", json.dumps(manifest, indent=2).encode(), "application/json")
    pruned = []
    for old in snapshots(target, prefix)[:-keep] if keep else []:
        target.delete_prefix(f"{prefix}/{old}")
        pruned.append(old)
    manifest["pruned"] = pruned
    return manifest


def read_snapshot(source, snapshot="latest", prefix="backups"):
    available = snapshots(source, prefix)
    if not available:
        raise BackupError("No complete backup was found in that location.")
    snapshot = available[-1] if snapshot == "latest" else snapshot
    if snapshot not in available:
        raise BackupError(f"Backup {snapshot} was not found. Available: {', '.join(available[-5:])}")
    manifest = json.loads(source.get_bytes(f"{prefix}/{snapshot}/manifest.json"))
    dump = source.get_bytes(f"{prefix}/{snapshot}/database.json.gz")
    if hashlib.sha256(dump).hexdigest() != manifest["database_sha256"]:
        raise BackupError("The database file in this backup is damaged (checksum mismatch).")
    return manifest, json.loads(gzip.decompress(dump))


def restore_backup(source, db, storage, snapshot="latest", prefix="backups", verify=True):
    """Restore into an EMPTY database and storage. Files are restored before rows,
    so the database never points at a missing file."""
    manifest, tables = read_snapshot(source, snapshot, prefix)
    with db.connect() as c:
        occupied = [t for t in TABLES if c.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]]
    if occupied:
        raise BackupError(f"The target database is not empty ({', '.join(occupied)}). Restore into a new, empty database.")
    restored_files = 0
    for item in manifest["objects"]:
        if storage.size(item["key"]) != item["bytes"]:
            transfer(source, f"{prefix}/objects/{item['key']}", storage, item["key"])
            restored_files += 1
    with db.connect() as c:
        for table in TABLES:
            data = tables.get(table, {"columns": [], "rows": []})
            if not data["rows"]:
                continue
            names = ",".join(data["columns"])
            marks = ",".join("?" for _ in data["columns"])
            for row in data["rows"]:
                c.execute(f"INSERT INTO {table} ({names}) VALUES ({marks})", row)
        counts = {t: c.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"] for t in TABLES}
    if counts != manifest["tables"]:
        raise BackupError(f"Restored row counts {counts} do not match the backup {manifest['tables']}.")
    report = {"snapshot": manifest["snapshot"], "tables": counts, "files_restored": restored_files,
              "files_in_backup": len(manifest["objects"])}
    if verify:
        report["verification"] = verify_files(db, storage)
    return report


def verify_files(db, storage):
    """Every file a document refers to exists; videos with a recorded checksum still match it."""
    missing, mismatched, checked = [], [], 0
    with db.connect() as c:
        documents = [json.loads(r["data"]) | {"_kind": r["kind"]} for r in c.execute("SELECT kind,data FROM documents").fetchall()]
    with tempfile.TemporaryDirectory(prefix="trendforge-verify-") as scratch:
        for doc in documents:
            for kind, field in FILE_FIELDS:
                if doc["_kind"] != kind or not doc.get(field):
                    continue
                if storage.size(doc[field]) is None:
                    missing.append(doc[field])
                    continue
                checked += 1
                if doc.get("sha256") and field in {"file_ref", "mp4_ref"} and kind in {"asset", "edited_video", "export"}:
                    with Path(storage.fetch(doc[field], scratch)).open("rb") as stream:
                        if hashlib.file_digest(stream, "sha256").hexdigest() != doc["sha256"]:
                            mismatched.append(doc[field])
    return {"files_checked": checked, "missing": missing, "checksum_mismatches": mismatched,
            "ok": not missing and not mismatched}
