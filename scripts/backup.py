"""Back up the TrendForge database and stored videos.

    uv run python -m scripts.backup                      # into the configured storage, under backups/
    uv run python -m scripts.backup --to-dir D:/tf-backup  # into a folder (another disk, NAS, ...)
    uv run python -m scripts.backup --keep 30            # keep the 30 newest snapshots

Uses the database and storage configured in .env. Safe to run while the website is open.
"""
import argparse
import json
import time

from trendforge.backup import create_backup
from trendforge.config import DATA
from trendforge.db import Database
from trendforge.storage import LocalStorage, create_storage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--to-dir", help="Write the backup into this folder instead of the configured storage")
    parser.add_argument("--prefix", default="backups")
    parser.add_argument("--keep", type=int, default=14, help="Snapshots to keep (older ones are removed; 0 keeps all)")
    args = parser.parse_args(argv)
    db = Database(DATA / "trendforge.sqlite3")
    storage = create_storage(DATA)
    target = LocalStorage(args.to_dir) if args.to_dir else storage
    started = time.monotonic()
    manifest = create_backup(db, storage, target, args.prefix, args.keep)
    print(json.dumps({"snapshot": manifest["snapshot"], "tables": manifest["tables"],
                      "files": len(manifest["objects"]), "files_copied": manifest["objects_copied"],
                      "pruned": manifest["pruned"], "seconds": round(time.monotonic() - started, 2)}, indent=2))


if __name__ == "__main__":
    main()
