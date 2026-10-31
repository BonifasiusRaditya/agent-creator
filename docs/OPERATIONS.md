# TrendForge operations: storage, worker, backup and restore

## Components

| Part | Runs where | Holds |
|---|---|---|
| Website + API (`trendforge.app`) | Local PC now; Vercel later | Nothing on disk that must survive (accounts and projects are in the database) |
| Database | Turso (or local SQLite) | Accounts, projects, documents, jobs (the job queue), events |
| Video storage | Tencent COS (or the local data folder) | Uploaded clips, finished edits, drafts, audio, exports, SRT |
| Video worker (`trendforge.worker`) | Inside the website process (local) or a separate machine/container | Temporary job files, worker logs (7 days), the speech model |

Videos never pass through the website when COS is used: the browser uploads with a short-lived signed
POST (COS rejects anything over 100 MiB), and downloads/previews use signed links valid for 15 minutes.
The website checks ownership before creating any link.

## Job queue and worker

- Starting work creates a queued job in the database. A worker claims it atomically, renews a 60-second
  lease every 2 seconds, and checks for cancellation at each renewal.
- Upload checks (`ingest`: format, codec, size, duration, checksum) run in a separate lane so they do
  not wait behind long renders. Each project runs at most one video job at a time; other projects queue.
- If a worker dies, its job is marked failed with `INTERRUPTED` once the lease expires (about a minute),
  never left "running". Queued jobs survive restarts.
- Idle workers poll the database less often (up to every 5 s); an embedded worker is woken immediately
  when a job is created.

Run a separate worker:

```powershell
# On the same machine (shares .env):
$env:TRENDFORGE_WORKER = "external"   # for the website process, so it does not start its own worker
uv run trendforge                       # terminal 1
uv run python -m trendforge.worker      # terminal 2
```

```bash
# As a container (any Linux host with Docker, e.g. Tencent Cloud Lighthouse/CVM):
docker build -f Dockerfile.worker -t trendforge-worker .
docker run -d --name trendforge-worker --restart unless-stopped \
  --env-file .env.worker -v trendforge-work:/work trendforge-worker
```

`.env.worker` needs `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `TRENDFORGE_STORAGE_BACKEND=cos` and the
four `TRENDFORGE_COS_*` values. With a separate worker the website must use `cos` storage (a worker on
another machine cannot read the website's disk). Connections shows whether a worker is online. The
speech model is downloaded once per worker (Connections → Download model, as an admin) into `/work`.

## Tencent COS setup

1. Create a **private** bucket (e.g. `trendforge-1250000000`) in a region close to your users.
2. Create a CAM sub-user with programmatic access and a policy limited to that bucket
   (`cos:PutObject`, `cos:PostObject`, `cos:GetObject`, `cos:HeadObject`, `cos:DeleteObject`,
   `cos:GetBucket` [list], multipart actions). Put its SecretId/SecretKey in `.env`.
3. Bucket **CORS**: allow origin = your website URL(s) (e.g. `http://127.0.0.1:8765`, later the Vercel domain),
   methods `GET, POST, HEAD`, headers `*`, expose `ETag`, max-age 600.
4. Recommended: enable **versioning** (deleted or overwritten objects can be recovered) and a lifecycle
   rule that removes non-current versions after 30 days.
5. Move existing local videos: stop the website, set `TRENDFORGE_STORAGE_BACKEND=cos`, then
   `uv run python -m scripts.migrate_storage` (preview) and `--apply`.

## Backup

```powershell
uv run python -m scripts.backup                       # into the configured storage, under backups/
uv run python -m scripts.backup --to-dir D:/tf-backup # into a folder on another disk
```

A snapshot contains every database row except sessions and sign-in counters (everyone signs in again
after a restore) plus a copy of every stored video under `backups/objects/`. Storage keys are never
overwritten, so each run copies only new files. `manifest.json` is written last; a snapshot without it
is ignored. `--keep` (default 14) removes older snapshots' database dumps.

Schedule it daily, e.g. on the worker host:

```bash
# crontab -e   (02:00 every day)
0 2 * * * docker run --rm --env-file /opt/trendforge/.env.worker trendforge-worker /app/.venv/bin/python -m scripts.backup >> /var/log/trendforge-backup.log 2>&1
```

Turso also offers point-in-time restore on some plans; it is a useful extra but not required: the
logical backup above restores into any empty Turso database or SQLite file.

## Restore

Restore always targets an **empty** database and storage, so a mistake can never merge into or
overwrite live data.

1. Stop the website and worker.
2. Create a new Turso database (and, for a full disaster, a new bucket) and point `.env` at them.
3. `uv run python -m scripts.restore --list` then `uv run python -m scripts.restore --snapshot latest`
   (add `--from-dir D:/tf-backup` when the backup is in a folder).
4. The restore copies files first, then rows, checks row counts against the manifest, confirms every
   referenced file exists and compares SHA-256 checksums of clips, finished edits and exports.
   It exits with an error if anything is missing or damaged.
5. Start the services and sign in again.

## Restore drill

Automated in `tests/test_storage_backup.py` and run with every test suite:

| Step | Check |
|---|---|
| Create an account, a project, an approved brief and a real uploaded clip | Upload accepted by the worker |
| Back up to a separate location, then back up again | Second backup copies 0 files (incremental) |
| Delete the project through the website | Rows and stored files are gone |
| Restore into a brand-new database and storage folder | Project, owner and clip restored; SHA-256 matches; no sessions restored |
| Restore again into the now non-empty database | Refused |
| Tamper with a backed-up video / the database dump | Verification fails / restore refused ("damaged") |
| Keep 2 of 3 snapshots | Oldest pruned |

COS-specific behaviour (signed upload policy, direct upload, worker download from the bucket, signed
download redirect, prefix deletion, server-side copy) is tested against an S3 emulator (moto).
A drill against a real COS bucket and Turso database is part of the deployment checklist; record its
duration there as the measured recovery time.

**Targets.** Recovery point: up to 24 hours with a daily backup (COS versioning narrows it for files).
Recovery time: the drill duration on the real services, dominated by copying video files.
