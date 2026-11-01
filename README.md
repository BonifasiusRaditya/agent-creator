# TrendForge

Create source-grounded content with a Planner, Writer and Reviewer. Built for beginner creators who want useful ideas, less production time and confidence in what they share.

The English interface uses a black and orange theme. The current product-launch workflow creates short-video scripts, social captions and marketplace listings in Bahasa Indonesia, English and Mandarin. Every factual line cites the supplied product sheet. Review failures return to the Writer, with at most three rounds before human escalation. Only the creator approves and exports.

## Run

Python 3.12/3.13 and uv:

```powershell
uv sync --python 3.12 --group dev
uv run trendforge
```

Open http://127.0.0.1:8765. Keep one server per data folder. Restart an existing server yourself after updating the code and .env.

## Configure once

Copy `.env.example` to `.env` only for a new installation. Preserve an existing .env.

```dotenv
TRENDFORGE_AI_ENGINE=gemini
GEMINI_API_KEY=your-private-google-ai-studio-key
GEMINI_MODEL=gemini-3.5-flash-lite
TURSO_DATABASE_URL=libsql://your-database.turso.io
TURSO_AUTH_TOKEN=your-private-turso-token
TRENDFORGE_INVITE_CODE=a-long-random-invite-code
TRENDFORGE_ADMIN_USERNAMES=your-username
```

Credentials stay on the backend. Use an eligible Gemini free-tier project. Google determines eligibility, billing and quota; the program never switches to a different paid model. Free-tier source content may be used to improve Google's products: use public or fictional product facts. Model 2.5 Flash-Lite returned 404 for the tested new account; 3.5 Flash-Lite succeeded. [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [native generation API](https://ai.google.dev/api/generate-content).

Turso is selected automatically when its URL/token are configured. A failed Turso connection never silently falls back to SQLite. Without those credentials, local SQLite is supported. Keys for the earlier YouTube/stock integrations remain compatible but are unnecessary for this source-only workflow.

## Create and review

1. Register with your invite code, or sign in to your existing account. No default production password is created.
2. Create a project and paste one verified fact per line. Choose at least two formats and your languages. Only attest halal evidence when you have checked a current certificate.
3. Save the source, then select Create & review. Follow the three agents and inspect cited rejections, repairs and evidence.
4. If the team escalates, clarify the source/angle or edit the draft and submit a new review. Invalid agent results, quota errors and timeouts never approve content.
5. Review all output, tick the confirmation and approve the exact revision. Download a ZIP with text, SVG covers, source/rule snapshots and the audit. Upload manually wherever you choose.
6. Edits always trigger fresh review. Tone preferences inferred from edits remain proposals until separately approved. Approved examples from your own projects guide future drafts.

## WorkBuddy

Gemini runs directly from the website. To use WorkBuddy instead, select `TRENDFORGE_AI_ENGINE=workbuddy` in .env and restart. In Connections generate your personal connector configuration and install it in WorkBuddy. The backend must remain reachable from that WorkBuddy process. Start a website run and copy its WorkBuddy task. The five MCP tools exchange each role's schema-validated result; human approval/export are deliberately absent. Connector tokens can be revoked through the existing tokens API.

Read [the workflow skill](workbuddy/skills/trendforge/SKILL.md), [architecture and API](docs/CREATOR_ARCHITECTURE.md), [accountability sheet](docs/ACCOUNTABILITY.md), and [Challenge C evidence/submission guide](docs/CHALLENGE_C.md).

## Verification

```powershell
uv run pytest -q
uv run python -m scripts.check_creator_live
```

The second command intentionally calls Gemini with fictional data on an isolated SQLite database and saves real provider evidence under `test-results/creator-live`. It does not change application accounts or projects. It creates a local test account `creator-tester` / `CreatorLocalTest!2026` only in that test database. Standard tests simulate model responses; Turso destructive tests require a separate test database and refuse the production URL.

Existing video endpoints/data remain compatible, while the current navigation and MCP toolset focus on Challenge C. Previous setup documentation is archived in [the legacy reference](docs/LEGACY_VIDEO_WORKSPACE.md). Existing multi-user accounts continue to use their original passwords. Older unowned projects require the explicit claim procedure in that reference.
