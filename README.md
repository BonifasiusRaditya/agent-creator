# TrendForge

Create source-grounded content and finished vertical videos with a Planner, Writer and Reviewer. Built for beginner creators who want useful ideas, less production time and confidence in what they share.

The English interface uses a black and orange theme. The workflow researches YouTube for creative inspiration, creates source-grounded scripts/captions/listings in Bahasa Indonesia, English and Mandarin, reviews them, then produces an MP4 from 3–5 uploaded clips. Review failures return to the Writer, with at most three rounds before human escalation. Only the creator approves and releases content.

## Run

Python 3.12/3.13 and uv:

```powershell
uv sync --python 3.12 --extra video --group dev
uv run --extra video trendforge
```

Open http://127.0.0.1:8765. Keep one server per data folder. Restart an existing server yourself after updating the code and .env.

## Configure once

For Vercel deployment, follow [VERCEL.md](docs/VERCEL.md). The default dependency set is web-only; local rendering and external workers require the `video` extra. A successful web build does not replace the external video worker or shared file storage.

Copy `.env.example` to `.env` only for a new installation. Preserve an existing .env.

```dotenv
TRENDFORGE_AI_ENGINE=workbuddy
TRENDFORGE_AGENT_BUDGET_SECONDS=180
TURSO_DATABASE_URL=libsql://your-database.turso.io
TURSO_AUTH_TOKEN=your-private-turso-token
TRENDFORGE_ADMIN_USERNAMES=
```

The Planner, Writer and Reviewer run in WorkBuddy, which uses its own signed-in account and model, so TrendForge needs no AI API key. Credentials stay on the backend. `TRENDFORGE_AGENT_BUDGET_SECONDS` is the total time for one run across all roles and review rounds (default 180, allowed 30–3600). Gemini is no longer supported; a `.env` that still selects it stops at startup with a clear message.

Registration is public and requires only a username and password. The obsolete `TRENDFORGE_INVITE_CODE` setting is ignored and can be removed. For a new installation, register the owner first, then add that existing username to `TRENDFORGE_ADMIN_USERNAMES` and restart/redeploy. Names in this list are reserved against public registration; existing accounts can still sign in.

Turso is selected automatically when its URL/token are configured. A failed Turso connection never silently falls back to SQLite. Without those credentials, local SQLite is supported. Keys for the earlier YouTube/stock integrations remain compatible but are unnecessary for this source-only workflow.

## Create and review

1. Create an account with a username and password, or sign in to your existing account. Registration signs you in automatically. No default production password is created.
2. Create a project and paste one verified fact per line. Choose at least two formats and your languages. Only attest halal evidence when you have checked a current certificate.
3. Save the source, then select Create & review. Follow the three agents and inspect cited rejections, repairs and evidence.
4. If the team escalates, clarify the source/angle or edit the draft and submit a new review. Invalid agent results, quota errors and timeouts never approve content.
5. Review all output, tick the confirmation and approve the exact revision. Download a ZIP with text, SVG covers, source/rule snapshots and the audit. Upload manually wherever you choose.
6. Edits always trigger fresh review. Tone preferences inferred from edits remain proposals until separately approved. Approved examples from your own projects guide future drafts.

The Projects page and each project show a six-step guide: **Source → Generate → Review → Approve → Video → Export**, with an explanation of each step and the current project stage. Video is optional; approved text can be downloaded directly.

## Make a finished video

1. Optionally open **Trend research**, search YouTube and select up to 10 creative references. Save Source & rules afterward. Titles and channel metadata guide creative angles; factual claims still use your product facts only.
2. After approving a Short-video script, open **Video studio** or **Make a video**. Select a script language and 30/45/60-second target, then confirm **Use approved script**.
3. Upload 3–5 owned/licensed H.264 MP4/MOV clips, 3–120 seconds each, up to 100 MiB per clip. Total footage must cover the chosen target. Optional stock search uses the existing configured Pixabay/Pexels key and retains provenance.
4. Select **Create automatic cut**, or edit each clip's order and trim points. Approve the cut, then **Render draft & generate subtitles**. FFmpeg fits framing into 9:16, joins/trims the clips, applies opening/closing fades and normalizes original audio.
5. Listen to the draft and correct actual faster-whisper Indonesian transcription. Save edits, check the review confirmation and approve subtitles. No-speech videos require an explicit no-speech decision. The proposed script is never substituted for the transcript.
6. Select **Export MP4**, preview the result, and download MP4/SRT plus the approved posting caption. The output is 1080×1920, 30 fps, H.264/AAC with burned-in approved subtitles. Upload manually to Shorts/Reels.

Content/source changes invalidate the linked video brief and downstream release. Processing, export and download enforce the current approved script, including evidence validity. Existing uploaded assets remain reusable; previous files cannot be released against an unapproved replacement source.

For a single local server set `TRENDFORGE_WORKER=embedded` (default). A configured external worker must be started separately with `uv run --extra video python -m trendforge.worker` using the same database/storage. The speech model downloads once and is cached; it needs no API key. The video uses the creator's actual clips and audio; optional generative video and TTS services are not required.

See [complete video acceptance evidence](docs/COMPLETE_VIDEO.md), including an actual browser-uploaded speech/ASR/export run and its limits.

## WorkBuddy

WorkBuddy is the AI engine (`TRENDFORGE_AI_ENGINE=workbuddy`, the default).

1. In **Connections**, select **Download WorkBuddy package**. The zip holds `mcp.json` with a personal connector token, the TrendForge skill and an icon. Keep it private; each download creates a new token, which you can revoke on the same page.
2. In WorkBuddy desktop, add the `trendforge` MCP server from `mcp.json` and install `skills/trendforge/SKILL.md`. After updating TrendForge, reinstall the skill from a fresh package.
3. Keep the TrendForge server running; the connector calls it. Ask WorkBuddy to call `trendforge_health` to confirm engine `workbuddy`.
4. Start a run on the website (**Create & review**), copy its WorkBuddy task and paste it into WorkBuddy. The five MCP tools exchange each role's schema-validated result; human approval/export are deliberately absent.

The connection banner appears across the signed-in website and refreshes every 15 seconds, with a manual **Refresh status** button. **WorkBuddy connected recently** means an authenticated personal connector contacted TrendForge within the last ten minutes, using persisted activity on unrevoked tokens. Generating a package or selecting the engine alone never counts as a connection. An older contact asks for a new check; ask WorkBuddy to run `trendforge_health`. This reports recent connector activity, not continuous desktop availability or completed agent execution.

An OpenAI-compatible provider remains available as an optional fallback (`TRENDFORGE_AI_ENGINE=openai_compatible` with `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`).

Read [the workflow skill](workbuddy/skills/trendforge/SKILL.md), [architecture and API](docs/CREATOR_ARCHITECTURE.md), [accountability sheet](docs/ACCOUNTABILITY.md), and [Challenge C evidence/submission guide](docs/CHALLENGE_C.md).

## Verification

```powershell
uv run --extra video pytest -q
$env:TRENDFORGE_TOKEN = "<a connector token from Connections>"; uv run python -m scripts.check_connector
```

The second command is a read-only check of the WorkBuddy connector against your running server: it confirms the five MCP tools and calls `trendforge_health`. Standard tests simulate agent responses; Turso destructive tests require a separate test database and refuse the production URL.

Existing video endpoints/data remain compatible. The website now includes both the Challenge C content flow and Video studio; MCP tools retain the agent-only workflow and cannot release a connected creator video's files. Previous setup documentation is archived in [the legacy reference](docs/LEGACY_VIDEO_WORKSPACE.md). Existing multi-user accounts continue to use their original passwords. Older unowned projects require the explicit claim procedure in that reference.
