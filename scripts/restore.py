"""Restore a TrendForge backup into an EMPTY database and storage, then verify it.

    uv run python -m scripts.restore --list
    uv run python -m scripts.restore --snapshot latest
    uv run python -m scripts.restore --from-dir D:/tf-backup --snapshot 20261101T020000000000Z

The target is the database and storage configured in .env (point them at a new, empty
Turso database / bucket first). Stop the website and worker while restoring.
"""
import argparse
import json
import sys
import time

from trendforge.backup import BackupError, restore_backup, snapshots
from trendforge.config import DATA
from trendforge.db import Database
from trendforge.storage import LocalStorage, create_storage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-dir", help="Read the backup from this folder instead of the configured storage")
    parser.add_argument("--prefix", default="backups")
    parser.add_argument("--snapshot", default="latest")
    parser.add_argument("--list", action="store_true", help="List complete snapshots and exit")
    parser.add_argument("--no-verify", action="store_true", help="Skip checksum verification of restored videos")
    args = parser.parse_args(argv)
    storage = create_storage(DATA)
    source = LocalStorage(args.from_dir) if args.from_dir else storage
    if args.list:
        print("\n".join(snapshots(source, args.prefix)) or "No complete backups found.")
        return
    started = time.monotonic()
    try:
        report = restore_backup(source, Database(DATA / "trendforge.sqlite3"), storage, args.snapshot,
                                args.prefix, verify=not args.no_verify)
    except BackupError as exc:
        print(f"Restore stopped: {exc}", file=sys.stderr)
        raise SystemExit(1)
    report["seconds"] = round(time.monotonic() - started, 2)
    print(json.dumps(report, indent=2))
    if not report.get("verification", {"ok": True})["ok"]:
        raise SystemExit("Restore finished, but verification found missing or damaged files (see above).")


if __name__ == "__main__":
    main()
