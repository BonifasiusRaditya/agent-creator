"""Copy videos from the local data folder to the configured object storage (Tencent COS).

    uv run python -m scripts.migrate_storage           # preview
    uv run python -m scripts.migrate_storage --apply   # copy

Stored references stay the same (keys mirror local paths), so no database change is needed.
Local files are kept; remove them yourself after checking the website. Stop the website and
worker first, then set TRENDFORGE_STORAGE_BACKEND=cos.
"""
import argparse
import json

from trendforge.config import DATA
from trendforge.storage import MEDIA_PREFIXES, LocalStorage, S3Storage, create_storage


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    target = create_storage(DATA)
    if not isinstance(target, S3Storage):
        raise SystemExit("Set TRENDFORGE_STORAGE_BACKEND=cos and the COS settings in .env first.")
    source = LocalStorage(DATA)
    files = [(k, s) for prefix in MEDIA_PREFIXES for k, s in source.list(prefix.rstrip("/"))]
    pending = [(k, s) for k, s in files if target.size(k) != s]
    print(json.dumps({"local_files": len(files), "to_copy": len(pending),
                      "bytes_to_copy": sum(s for _, s in pending), "apply": args.apply}, indent=2))
    if args.apply:
        for key, _ in pending:
            target.put_file(key, source.path(key))
        missing = [k for k, s in files if target.size(k) != s]
        print("All files copied and verified by size." if not missing else f"Not copied: {missing}")


if __name__ == "__main__":
    main()
