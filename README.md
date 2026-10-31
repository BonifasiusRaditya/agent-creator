# TrendForge

A local creator workspace for finding inspiration, drafting original video scripts and posting captions, and adding Indonesian subtitles. Bring a finished edit from your favorite app, or try the optional built-in video editor.

The interface is in English. Briefs can be written in English or Indonesian. Speech transcription targets Indonesian.

## Run

Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/) are required. FFmpeg is included through the installed media package; a system FFmpeg can also be used.

From this folder:

```powershell
uv sync --python 3.12 --group dev
uv run trendforge
```

Alternatively, run `start.ps1` in PowerShell. Open **http://127.0.0.1:8765** and create an account (see **Accounts** below). The service listens only on this device.

For another port:

```powershell
uv run trendforge --port 8767
```

Keep one server instance per data folder. Stop the service with Ctrl+C before restarting it.

## Accounts

Each creator has a username and password, and sees only their own projects, footage, exports and WorkBuddy requests. Accounts are stored in the database (Turso or SQLite), so the same account works from any device that reaches the server.

```dotenv
TRENDFORGE_INVITE_CODE=a-long-random-shared-code
TRENDFORGE_ADMIN_USERNAMES=your-username
```

- **Registration** requires the shared invite code. Leave `TRENDFORGE_INVITE_CODE` empty to close registration; existing accounts can still sign in.
- **Usernames** are 3–32 letters, numbers, dots, dashes or underscores, case-insensitive. Passwords are 8–200 characters, stored only as scrypt hashes.
- **Sign-in protection:** five failed attempts lock that username for 15 minutes; wrong invite codes are limited workspace-wide. Error messages do not reveal whether a username exists.
- **Admins** (listed in `TRENDFORGE_ADMIN_USERNAMES`) change shared workspace settings such as the speech model. Other creators see those settings read-only.
- **Change password** in Connections → Your account. Your other devices are signed out.

**Upgrading an existing workspace.** The old single workspace password is no longer used, and projects created before accounts have no owner, so no account sees them. Register your account, stop the server, then assign those projects to it:

```powershell
uv run python -m scripts.claim_projects --username your-username          # preview
uv run python -m scripts.claim_projects --username your-username --apply
```

## Turso database

Set `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` in the project `.env`. `db.py` automatically selects Turso when either setting is nonempty and requires both valid values; connection failures never fall back to SQLite. `TRENDFORGE_DATABASE_BACKEND=sqlite` explicitly selects local storage for isolated tests or local operation. `turso` explicitly requires the remote database. The official `libsql` Python driver is locked in `uv.lock`.

The backend creates its tables and indexes with `IF NOT EXISTS` and adds new columns to existing databases in place. Queries use bound parameters; nested database contexts share the same transaction. Accounts (hashed passwords), sessions, connector tokens (hashed) and project records live in the selected database; encrypted legacy settings, video files and models remain on disk. Keep one application instance per workspace.

An already running server must be restarted to load the database changes. For an existing workspace, stop it before migration. Preview with `uv run python -m scripts.migrate_to_turso`. After approval to transfer project metadata, `uv run python -m scripts.migrate_to_turso --apply` backs up the local database, copies accounts, connector tokens, projects, documents, jobs and events into an empty remote workspace in one transaction, and checks row counts. It refuses nonempty destinations or active local jobs. Existing login sessions are not exported. The original database and local media remain; sign in again after switching.

## Configure services once

Copy `.env.example` to `.env` in this project folder, then fill in the service keys:

```dotenv
TRENDFORGE_AI_ENGINE=workbuddy
YOUTUBE_API_KEY=your-youtube-data-api-key
PEXELS_API_KEY=your-optional-pexels-key
TRENDFORGE_STOCK_PROVIDER=pixabay
PIXABAY_API_KEY=your-optional-pixabay-key
```

`.env` is loaded automatically from the project folder, even when the service is launched from another directory. Restart TrendForge after editing it. Existing process variables override `.env`; `.env` overrides previously saved local settings. An explicit empty value disables a service, including any older saved key. Omitted settings retain their saved value or default. Values are loaded literally, without `${...}` interpolation. Never commit a filled `.env`; it is excluded from source control and contains plaintext secrets.

Enable YouTube Data API v3 for the Google Cloud project that owns the key. YouTube supplies public metadata, not footage. Stock footage is optional. Pixabay is the temporary default; get a key at https://pixabay.com/api/docs/ after signing in and set `PIXABAY_API_KEY` in `.env`. Restart, then use **Connections → Pixabay footage → Test connection** and **Footage → Find stock footage**. Do not enter a Pixabay key as `PEXELS_API_KEY`. To switch back later, set `TRENDFORGE_STOCK_PROVIDER=pexels` and configure `PEXELS_API_KEY`; existing imported clips keep their original source credits. There is no silent fallback between providers.

Pixabay searches are cached locally for 24 hours (including across restarts), per its API requirements. Search cards link to Pixabay and creator/source credits remain attached to imports. Eligible clips are 3–120 seconds and at most 100 MiB, with a short edge of at least 360 px and a long edge of at most 1920 px; final codec validation happens on import. Portrait results are preferred when available; landscape footage is fitted by the existing editor. Speech recognition runs locally with faster-whisper and needs no API key; select and download a multilingual model in **Connections** once.

**Creators do not enter API keys in the website.** Connections shows service availability, connection checks, the WorkBuddy setup, and local speech models. Environment-managed values cannot be silently overridden through the settings API. Old encrypted connection settings remain supported as a fallback for existing installations; the interface no longer asks creators to edit them.

## WorkBuddy is the primary AI

WorkBuddy does the reasoning and writes the original ideas, hooks, briefs, scripts and shot lists. TrendForge exposes its project and production tools through the official local **MCP + Skill** connector pattern. There is no invented WorkBuddy model HTTP endpoint and no WorkBuddy API key to enter in TrendForge.

1. Run TrendForge and sign in to WorkBuddy with your own account.
2. In **Connections**, download the connector package, or copy its configuration into WorkBuddy's local MCP settings and install the included `trendforge` skill. The package generated by the website uses the running installation's executable, project folder, data folder, and service URL.
3. In a project, select **Create with WorkBuddy**. Copy the saved task into WorkBuddy with the connector enabled.
4. WorkBuddy reads the task context/schema, creates three original ideas, and calls `save_agent_result`. The website refreshes when the result is actually saved.
5. Choose an idea and send the brief task to WorkBuddy in the same way. Review and approve the resulting script/shot list here.

You can also start or resume the whole workflow conversationally in WorkBuddy using the connector. `list_agent_requests` finds pending website tasks. No AI request runs just because it is queued: WorkBuddy must be open, signed in, connected, and instructed to complete it. The website clearly shows that waiting state. This integration does not automatically open a WorkBuddy chat or impersonate its account.

Results are schema-checked and tied to the exact project revision and selected research sources. Stale/cancelled tasks cannot overwrite a changed project. Repeated identical saves are safe. The connector cannot grant human approval.

The optional OpenAI-compatible writing adapter is retained for previously requested compatibility, but is **off by default** and is never a silent fallback. To enable it explicitly, set `TRENDFORGE_AI_ENGINE=openai_compatible`, `AI_BASE_URL`, `AI_MODEL`, and optional `AI_API_KEY` in `.env`. Remote providers require HTTPS; a localhost provider may use HTTP. This path uses `/chat/completions` and validates structured responses.

## Create your content draft

1. Create a project with topic, audience, goal, target duration, platform and writing language.
2. Find YouTube references across multiple searches. Select up to 10 saved references, or use your own topic.
3. Generate ideas and develop a brief/script with your configured AI, or write manually. Review and approve the brief.
4. Draft a posting caption on the Brief page. Generate with the configured writing provider, edit, save and copy it. Copy your script for your own editor.
5. Optionally collect footage (including Pixabay stock) on Footage. Download clips for your external editor when needed.
6. On **Footage**, upload a finished edit to go directly to subtitles, or select **Try out our new video editing feature!** to use the existing 3–5-clip editor.
7. Review the actual speech transcription and approve subtitles (or explicitly confirm no speech), then export MP4/SRT. Your caption remains available on Brief and Export.

You can stop after the brief and posting caption. Video assembly is optional. The built-in editor uses clip lengths and your approved sequence; it does not identify the best scenes. Uploaded finished edits keep their actual duration and cut sequence; we only normalize the output profile for subtitle export.

## Media limits

| Input | Supported |
|---|---|
| Clips per project | 3–5 |
| Container | MP4 or MOV |
| Video/audio | H.264 video; AAC or PCM audio, or no audio |
| Size | Up to 100 MiB per clip; 500 MiB per project |
| Length | 3–120 seconds per clip; at most 10 minutes total |
| Dimensions | Short edge at least 360 px; long edge at most 1920 px |
| Output length | 30, 45, or 60 seconds |

Outputs are 1080×1920, 30 fps, H.264/yuv420p MP4 with AAC 48 kHz stereo. The edit fits footage without stretching or silently cropping it, uses cuts between clips, and applies a short visual fade at the beginning and end. Speech subtitles are embedded in the MP4 and also available as SRT.

HEVC and 4K footage should be converted before uploading. Speech quality depends on the recording; names, numbers, and mixed-language speech need review.

## Connector setup and verification

`workbuddy/mcp.json` is a template. Create your real configuration in **Connections → Create connector configuration** (or **Download connector**): each one contains a new **personal connector token** (`TRENDFORGE_TOKEN`) that acts only on your projects, cannot approve anything, and cannot create more tokens. Treat it like a password; revoke unused or exposed tokens under **Connector tokens**. The package includes metadata, an icon, configuration and the agent skill, and no provider credentials.

The official MCP client has verified stdio initialization, tool discovery and real backend calls. Installation, login and actual generation inside your WorkBuddy account still need to be completed in WorkBuddy; protocol tests do not imply an authenticated WorkBuddy session.

## Video storage, worker and backups

Videos are stored in the local data folder (`TRENDFORGE_STORAGE_BACKEND=local`, default) or in **Tencent Cloud Object Storage** (`cos`). With COS, the browser uploads straight to the bucket with a short-lived signed form (COS itself refuses files over 100 MiB) and plays/downloads through 15-minute signed links; credentials stay on the server.

Video work runs in a **worker** that takes jobs from a queue in the database. Locally it runs inside the website process (`TRENDFORGE_WORKER=embedded`). For online use, run it separately with `uv run python -m trendforge.worker` or the `Dockerfile.worker` container. Every upload is checked by the worker (format, codec, size, duration, checksum) before it joins the project; the Footage page shows "Checking video…" meanwhile. Each project runs one video job at a time; other projects queue instead of being refused. A crashed worker's job is marked interrupted within about a minute; queued work survives restarts.

Back up the database and all stored videos with `uv run python -m scripts.backup` (incremental) and restore into an empty database and storage with `uv run python -m scripts.restore`, which verifies checksums. COS setup (bucket, CORS, versioning), migrating existing local videos, scheduling backups and the restore drill are described in `docs/OPERATIONS.md`.

## Storage and privacy

- FastAPI serves the browser interface and API. The database (Turso or SQLite) stores accounts, projects, revisions, approvals, the job queue and events.
- Clips, drafts, subtitle files and exports are stored in `.data/` by default, or in your COS bucket when configured. Speech models, worker logs and encrypted legacy settings stay in the local data folder. This folder is excluded from source control.
- Files follow the device's folder-sync settings. The current project is inside OneDrive; choose a non-synced location through `TRENDFORGE_DATA_DIR` if you want to keep runtime files out of folder synchronization.
- WorkBuddy receives project context, selected reference metadata and structured tool results. Uploaded video binaries are not included in writing requests. Its account and conversation retention follow WorkBuddy settings. The optional alternative writing provider receives writing context only when explicitly enabled. YouTube and the selected stock provider (Pixabay or Pexels) receive their respective search queries. Pixabay search metadata is cached under `.data/cache/stock/pixabay/` for 24 hours; credentials are not stored in those cache files.
- Deleting a project removes its application-managed files and records. Separately downloaded copies and WorkBuddy conversations are outside that deletion.
- YouTube metadata is removed after 30 days, including saved reference IDs. Diagnostic job logs expire after seven days. An automatic cleanup runs while the service is open and at startup.

Optional environment overrides:

```powershell
$env:TRENDFORGE_DATA_DIR = 'C:\path\to\your\private\TrendForge'
$env:FFMPEG_BINARY = 'C:\path\to\ffmpeg.exe'
uv run trendforge
```

Use that database's own accounts and a new connector configuration. Do not point two active server instances at the same data folder.

## Checks

```powershell
uv run pytest tests --basetemp=test-results/pytest -q
node --check trendforge/static/app.js
```

Tests use isolated data folders and synthetic video clips. They cover authentication, CSRF/origin protection, source/AI contract validation, revisions, file rejection, idempotency, real FFmpeg processing for 3-clip/30-second and 5-clip/60-second projects, subtitle burn-in pixel checks, SRT text, downloads, export history, and deletion. Provider contract tests simulate HTTP responses; they do not claim live access to an account without credentials.

To check the connector against a running server:

```powershell
uv run python scripts/check_connector.py
```

The app has also been exercised through the browser from project creation through upload, edit approval, subtitle review, final export, MP4 download, and ready-to-upload confirmation. A phone-sized viewport was checked for overflow. Real CPU speech inference was verified with the downloaded multilingual model and the official Whisper test sample; this is a runtime check, not a measured Indonesian accuracy benchmark.

## Recovery

- **WorkBuddy task waiting:** open WorkBuddy, enable the connector, and paste the saved task. The website cannot execute WorkBuddy on its own.
- **Service unavailable:** the workspace owner checks `.env` and enabled APIs, then restarts the service. Saved work and manual writing remain available.
- **Speech step failed:** download/check the model, then retry transcription from the existing valid draft. You can enter reviewed subtitle cues manually.
- **Job interrupted:** restart the service or the worker. Interrupted work is marked failed, not falsely complete. Retry from the saved plan or draft.
- **Video worker offline:** Connections shows the worker's status. Uploads and video jobs wait in the queue and run when it is back.
- **Cancel:** stops processing while preserving uploaded clips and valid checkpoints. This is not byte-level pause/resume.
- **File rejected:** follow the format/size/duration message and convert the source before re-uploading.
- **Low disk space:** remove projects you no longer need, then retry. The app does not silently delete your active footage.
- **Media failure details:** the job's `process.log` stays with the worker (`.data/jobs/<job-id>/`, or `logs/<job-id>.log` in the worker folder when videos are in COS). It is not sent to the AI provider.

Public hosting, multi-user access, automatic social publishing, video generation, and voice cloning are not included. Text-to-speech is optional in the PRD and is not exposed as an unfinished control.

See `docs/IMPLEMENTATION.md` for architecture, endpoint groups, and verification details. The original requirements remain in `PRD.md`.


## Inspiration-first workflow

Discover, scripts and posting captions are the core workflow. Up to 10 saved references can be selected per writing request, from any of your searches, so requests stay within the model's context. Larger selections are rejected with a clear message rather than silently cut. Only compact reference metadata (ID, title, channel, publish date, duration, link) is sent to the writing provider or WorkBuddy; thumbnails and statistics are not. Briefs saved before this limit keep their original references when edited. Searches accumulate in Discover. Pixabay remains the default stock provider.

After approving a brief, open **Footage**: upload a finished H.264 MP4/MOV edit (3–120 seconds, up to 100 MiB, 360–1920 px), or choose **Try out our new video editing feature!** to open the optional Edit phase and its existing 3–5-clip editor. Finished edits retain their actual duration, sequence and cuts; encoding fits them to 1080×1920/30fps without cropping. Subtitle review and export work with either path. A finished edit can be uploaded without uploading raw clips or creating an edit plan.

The Brief and Export screens include an editable, saved posting-caption draft with copy support. The configured OpenAI-compatible provider (including Gemini) can generate captions from the saved brief in the project language. WorkBuddy users can paste captions manually. Caption drafts are marked for review when their source brief changes; captions are never published automatically.
