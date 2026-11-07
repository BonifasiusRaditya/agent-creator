# Vercel web deployment

The web bundle excludes video libraries. `av`, `imageio-ffmpeg` and `faster-whisper` belong to the `video` optional dependency set. The external worker Dockerfile and local launcher explicitly install that set. `uv.lock` must be committed along with `pyproject.toml`.

`vercel.json` excludes outputs, test files, cache directories, documentation and nested node_modules from the Python bundle. `.vercelignore` also excludes these from deployment uploads. Source/static files required by the app remain included. The exact Linux bundle size must be confirmed by a Vercel build; a local import check is not a successful deployment.

## Dashboard

- Framework: FastAPI. Root directory: repository root.
- Build Command and Install Command: default, with overrides disabled. Output directory: default.
- Do not select all optional extras in a custom install command.
- Add credentials in Vercel Environment Variables, not browser code or Git. Local .env files are not deployment configuration.

Required web environment:

```dotenv
TURSO_DATABASE_URL=libsql://your-existing-database.turso.io
TURSO_AUTH_TOKEN=your-private-token
TRENDFORGE_AI_ENGINE=workbuddy
TRENDFORGE_WORKER=external
TRENDFORGE_DATA_DIR=/tmp/trendforge
TRENDFORGE_ALLOWED_HOSTS=your-project.vercel.app,your-custom-domain.example
TRENDFORGE_ADMIN_USERNAMES=
```

Use only your actual hostnames, without a scheme or path. System-provided VERCEL_URL / VERCEL_PROJECT_PRODUCTION_URL are also accepted. Unrelated Host headers remain blocked. Existing accounts stay in Turso. The temporary directory is only an instance cache/settings workspace, not persistent database or video storage. Keep shared service settings in environment variables.

Account creation is public with a username and password; no invite code is required. An old `TRENDFORGE_INVITE_CODE` variable has no effect and can be deleted. For a fresh installation, register the owner first, then add their existing username to `TRENDFORGE_ADMIN_USERNAMES` and redeploy. Public registration cannot claim names reserved by this list. Existing accounts and passwords continue to work.

The Vercel runtime automatically disables the embedded video worker. With WorkBuddy, each agent step arrives as its own short connector request, so the run budget (`TRENDFORGE_AGENT_BUDGET_SECONDS`, default 180) is not bound by the function limit; point the connector's `TRENDFORGE_URL` at the deployed site. If you switch to the optional `openai_compatible` engine, its run executes inside one function's BackgroundTasks, so set the budget to 100 or less to fit the configured 120-second function limit. This is bounded request execution, not a durable long-running job scheduler.

## Video needs an external worker and shared storage

Full video deployment is not provided by a smaller Lambda bundle alone. Configure the existing Tencent COS backend on both the web service and the worker:

```dotenv
TRENDFORGE_STORAGE_BACKEND=cos
TRENDFORGE_COS_BUCKET=your-existing-bucket
TRENDFORGE_COS_REGION=your-region
TRENDFORGE_COS_SECRET_ID=your-private-limited-key
TRENDFORGE_COS_SECRET_KEY=your-private-secret
```

The bucket needs browser-upload CORS for the actual website origin. Uploads go directly to object storage and video downloads use signed URLs, avoiding function payload limits. Vercel local storage is rejected for uploads. Start `Dockerfile.worker` on a persistent host with FFmpeg/Whisper, the same Turso and COS settings, and persistent scratch/model cache. The worker need not expose a public HTTP port. Video jobs report WORKER_OFFLINE instead of silently assuming a worker exists when none is online.

No new service account, API key, paid subscription or external deployment has been created by this change. If shared storage or a persistent host is not yet available, they still need to be arranged; do not interpret a successful Vercel build as a working video deployment. An alternative is hosting the complete application and embedded worker on one persistent machine with local storage.

## Local / worker installation

```powershell
uv sync --extra video --group dev
uv run --extra video trendforge
```

For an external worker: `uv run --extra video python -m trendforge.worker`.

References: [Python bundle configuration](https://vercel.com/docs/functions/runtimes/python#controlling-what-gets-bundled), [function payload limits](https://vercel.com/docs/functions/limitations#request-body-size).
