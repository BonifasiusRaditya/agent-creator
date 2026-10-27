# TrendForge

A local creator workspace that takes a topic and 3–5 clips through research, a content brief, a timed edit, Indonesian subtitles, and a finished vertical MP4.

The interface is in English. Briefs can be written in English or Indonesian. Speech transcription targets Indonesian.

## Run

Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/) are required. FFmpeg is included through the installed media package; a system FFmpeg can also be used.

From this folder:

```powershell
uv sync --python 3.12 --group dev
uv run trendforge
```

Alternatively, run `start.ps1` in PowerShell. Open **http://127.0.0.1:8765** and create your own workspace password. The service listens only on this device.

For another port:

```powershell
uv run trendforge --port 8767
```

Keep one server instance per data folder. Stop the service with Ctrl+C before restarting it.

## Connect your tools

Open **Connections** after signing in.

1. **AI writing:** enter your OpenAI-compatible API base URL, model ID, and API key. Include the provider's API prefix, usually `/v1`. Save, then use **Test connection**. A provider on `http://localhost` is supported; remote providers require HTTPS. The application uses `/chat/completions`, with a JSON response and a plain-JSON fallback for providers that do not support `response_format`.
2. **YouTube research:** enable YouTube Data API v3 in your Google Cloud project, add its API key, save, and test. Research uses public metadata, not downloads of YouTube footage. There is no social-account login or automatic publishing.
3. **Speech & subtitles:** select a multilingual speech model and download it once. Base is the default balance of speed and quality; Tiny and Small are also available. Downloading requires internet; an already downloaded model is loaded from disk. This workspace already contains the Base model used for verification.
4. **Pexels, optional:** add an API key to search and import eligible stock clips. Creator credits and source links remain attached to the imported clip.

Empty credential inputs preserve existing saved keys. Use the remove-key control and save to remove a key. Credentials are encrypted locally and never returned by the API. Keep the data folder and its encryption key private.

“Configured” means settings have been saved; **Test connection** makes a real provider request. AI and YouTube require your own credentials, which are not included. Their live account access has not been verified using your accounts.

## Make a video

1. Create a project with a topic, audience, goal, duration, platform, and writing language.
2. Find references and optionally select up to five, or continue with your own topic.
3. Generate three ideas through your configured AI provider. Develop one into a brief, or write the brief manually. Review the script and shot list, then approve the brief.
4. Confirm your rights to the footage and upload 3–5 clips.
5. Create an edit plan. Review the suggested timing, reorder the clips, and adjust the trim points. Approve the plan and create the draft.
6. Review the draft and its actual speech transcription. Edit subtitle text/timings, split long cues, or add manual cues when recovering from a failed transcription. If no speech is detected, explicitly confirm that the video can continue without subtitles.
7. Approve the subtitles, export, preview, and download your MP4 and SRT. Mark the finished video ready to upload once you have checked it.

The script is a production guide. It is never substituted for the transcript of the uploaded footage. Automatic editing uses clip lengths and the approved sequence; it does not claim to understand scenes or identify the best visual moments.

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

## Tencent WorkBuddy

The website and WorkBuddy use the same backend and saved projects.

1. Run TrendForge.
2. In Connections, select **Get connector configuration** and add that configuration in WorkBuddy's local MCP/connector settings. This generates the correct executable, data folder, and URL for your running installation.
3. Install the skill from `workbuddy/skills/trendforge/SKILL.md` alongside the connector.
4. Ask WorkBuddy to create or resume a project. It can research, save an original brief, prepare a timed edit, check jobs, and offer finished downloads.

Human approvals stay in the website. The connector does not expose approval tools and cannot approve on your behalf. It starts long-running jobs asynchronously and checks their persisted status.

`workbuddy/mcp.json` contains this installation's local configuration. Generate a fresh configuration from Connections when moving the folder or changing the port/data directory. No API keys or service tokens are included in that JSON.

The connector passed an actual stdio handshake, tool discovery, and a service call through the official MCP client. Import and account-specific access inside your WorkBuddy installation still need to be completed there.

## Storage and privacy

- FastAPI serves the browser interface and API. SQLite stores projects, revisions, approvals, jobs, and events.
- Clips, drafts, subtitle files, exports, models, and encrypted connection settings are stored in `.data/` by default. This folder is excluded from source control.
- Files follow the device's folder-sync settings. The current project is inside OneDrive; choose a non-synced location through `TRENDFORGE_DATA_DIR` if you want to keep runtime files out of folder synchronization.
- The configured AI provider receives the writing context and selected reference titles, not uploaded video binaries. YouTube receives research queries. Pexels receives optional stock queries.
- Deleting a project removes its application-managed files and records. Separately downloaded copies and WorkBuddy conversations are outside that deletion.
- YouTube metadata is removed after 30 days, including saved reference IDs. Diagnostic job logs expire after seven days. An automatic cleanup runs while the service is open and at startup.

Optional environment overrides:

```powershell
$env:TRENDFORGE_DATA_DIR = 'C:\path\to\your\private\TrendForge'
$env:FFMPEG_BINARY = 'C:\path\to\ffmpeg.exe'
uv run trendforge
```

Use the new folder's own setup password and connector configuration. Do not point two active server instances at the same data folder.

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

- **AI/YouTube unavailable:** check Connections; saved work remains. A manual brief is always available.
- **Speech step failed:** download/check the model, then retry transcription from the existing valid draft. You can enter reviewed subtitle cues manually.
- **Job interrupted:** restart the service. Interrupted work is marked failed, not falsely complete. Retry from the saved plan or draft.
- **Cancel:** stops processing while preserving uploaded clips and valid checkpoints. This is not byte-level pause/resume.
- **File rejected:** follow the format/size/duration message and convert the source before re-uploading.
- **Low disk space:** remove projects you no longer need, then retry. The app does not silently delete your active footage.
- **Media failure details:** the job's `process.log` is stored locally under `.data/jobs/<job-id>/`. It is not sent to the AI provider.

Public hosting, multi-user access, automatic social publishing, video generation, and voice cloning are not included. Text-to-speech is optional in the PRD and is not exposed as an unfinished control.

See `docs/IMPLEMENTATION.md` for architecture, endpoint groups, and verification details. The original requirements remain in `PRD.md`.

