# TrendForge implementation

## Architecture

```text
Browser (English HTML/CSS/JavaScript)
    ↕ same-origin session + CSRF
FastAPI project service ── SQLite documents, versions, jobs and events
    ├─ persisted writing requests ↔ WorkBuddy via local MCP + Skill (primary AI)
    ├─ HTTPX → OpenAI-compatible writing adapter (explicit optional mode only)
    ├─ HTTPX → YouTube Data API v3
    ├─ HTTPX → Pexels, when configured
    ├─ object storage: local data folder, or Tencent COS (signed direct upload/download)
    └─ job queue in the database (leases, heartbeats, cancellation)
         ↓ claimed by the video worker (embedded, or `python -m trendforge.worker` / Dockerfile.worker)
         ├─ ingest lane: validates uploads and stock clips (PyAV probe, limits, SHA-256)
         ├─ FFmpeg subprocesses → normalize, trim, combine, fade, encode
         ├─ PyAV → media metadata validation
         ├─ isolated faster-whisper subprocess → actual speech cues
         └─ libass → reviewed subtitles embedded in final MP4

WorkBuddy → local stdio MCP connector → the same FastAPI service
```

The UI has no separate build system or duplicate application server. Python dependencies are locked in `uv.lock`. FFmpeg is resolved from `FFMPEG_BINARY`, the system PATH, or the installed binary package. Media validation uses PyAV rather than requiring a separate ffprobe executable.

WorkBuddy is the default AI engine. Website writing actions persist a pending agent request, with project revision and selected source IDs. WorkBuddy reads the request/schema and submits its own generated result via MCP. A pending request is not executing until WorkBuddy handles it. The browser observes saved changes while preserving unsaved edits. Stale/cancelled requests cannot write; repeated identical submissions are idempotent. Human approvals remain operator-only. An explicitly enabled OpenAI-compatible adapter remains available without automatic fallback.

Service credentials load from the project `.env` at process startup using python-dotenv without interpolation. Precedence is process environment, `.env`, encrypted legacy settings, defaults. Explicit empty environment values disable services. Public responses expose configuration flags and sources, never keys. Environment-managed values reject settings API overrides. The frontend has no credential-entry forms.

## Implemented journey

| Requirement | Implementation |
|---|---|
| Project/context | Create, list, edit and delete projects; 30/45/60-second targets; English/Indonesian writing |
| YouTube research | Niche search, enrichment, optional chart, source timestamps, one-hour cache, manual path, safe failure messages |
| Ideas and script | Three schema-validated AI ideas; one structured brief/script/shot list; manual writing; revision and approval |
| Footage | Real multi-file uploads with progress/cancel; rights confirmation; server validation; preview/removal |
| Automatic edit | Duration allocation, sequencing, user trim controls, fit/pad, audio normalization, cuts and fade |
| Subtitles | Local Indonesian ASR from assembled audio; editable timed cues; long-cue splitting; manual recovery; no-speech confirmation |
| Export | Real MP4 and SRT; full decode/profile checks; browser range streaming and downloads; export history |
| Recovery | Single active job, idempotency, cancel, restart marking, preserved draft checkpoint for STT retry |
| Privacy | Local session/password; encrypted settings; CSRF/origin/host guards; safe input paths; deletion and retention |
| WorkBuddy | 21 typed MCP tools; persisted writing requests/results; project discovery, stock search, packaged skill/metadata; runtime connector download; no approval tools |
| Optional stock | Pexels search/import, approved host validation, same media validator, creator/source credits |

Automatic cuts are timing-based. The application does not claim visual scene understanding, full-platform trend coverage, or viral prediction. It does not rip public YouTube media.

## Main code

- `trendforge/app.py`: HTTP interface, authentication, project invariants, approval gates, upload and download paths.
- `trendforge/db.py`: SQLite persistence and job idempotency/concurrency constraints.
- `trendforge/models.py`: validated contracts, cue/trim rules, frame-based allocation.
- `trendforge/integrations.py`: real provider requests and safe error mapping.
- `trendforge/media.py`: worker, FFmpeg pipeline, output validation, SRT/ASS rendering.
- `trendforge/transcribe.py`: killable local speech process, downloaded-model reuse, VAD/cue conversion.
- `trendforge/mcp_server.py`: WorkBuddy MCP tools over stdio.
- `trendforge/static/`: complete English frontend, responsive layout, workflow forms and real API calls.

## Endpoint groups

The live OpenAPI schema is available at `/openapi.json`, and interactive API documentation at `/docs`. Authenticated mutations require a session CSRF token, or a personal connector bearer token for the operations assigned to it. Every `/api/v1/projects/{id}/…` route is checked once in middleware against the signed-in user (or the token's owner); another user's project responds as not found.

| Group | Main routes |
|---|---|
| Accounts | `GET/POST/DELETE /api/v1/session` (username + password), `POST /api/v1/auth/register` (invite code), `POST /api/v1/auth/password`, `GET/POST /api/v1/tokens`, `DELETE /api/v1/tokens/{id}` |
| Connections | `GET/PATCH /api/v1/settings`, test, connector configuration, speech-model download |
| Projects | `GET/POST /api/v1/projects`, `GET/PATCH/DELETE /api/v1/projects/{id}` |
| Research/writing | research runs, agent requests/context/schema/cancel/result, optional AI adapter, manual brief revisions, operator approval |
| Footage | asset upload/list/delete, authorized media streaming, optional stock search/import |
| Editing | automatic/manual plans and operator approval; prepare jobs |
| Subtitles | draft/media reads, transcription retry, cue revisions and operator approval |
| Output | export jobs, validated export history, MP4/SRT streams/downloads, ready confirmation |
| Job control | status and cancellation; asynchronous starts require `Idempotency-Key` |

Public responses omit internal file references, execution snapshots, credentials and service tokens. Failed media files are not published as exports. Export responses are included only when the producing job succeeded.

## Verification boundaries

Validation uses actual FastAPI, SQLite, FFmpeg, PyAV, libass and the MCP SDK. Both real-video integration profiles complete through download and project deletion. Subtitle rendering is checked in decoded frame pixels, not only by looking for an SRT file. Real speech inference has been executed on CPU.

The full UI has been tested on desktop and a 393×852 viewport. Browser testing exercised the actual file picker, upload progress, edit approval, asynchronous completion, no-speech confirmation, final video playback readiness, download, and ready confirmation. The final browser video reported 1080×1920, 30.004 seconds, readyState 4, and no playback error.

YouTube/Pexels account-specific live calls require owner-managed service credentials; WorkBuddy requires its own signed-in account. Alternative provider calls require explicitly enabled credentials. HTTP contract tests simulate these services to verify mapping, validation and failure handling. WorkBuddy's MCP protocol was verified with the official client; installation and login in a particular WorkBuddy account remain user setup. Indonesian transcription accuracy needs evaluation on representative Indonesian recordings; an English reference sample only verified the inference runtime.

No user video, API key, or fabricated performance telemetry is bundled as project content. Test clips and test-only workspaces live under ignored `test-results/` directories. The UI never presents seeded projects or synthetic research as real creator activity.

## References

- [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/)
- [WorkBuddy connectors](https://open.workbuddy.cn/en/docs/connector)
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html)
- [YouTube search API](https://developers.google.com/youtube/data/reference/rest/v3/search/list)
- [YouTube developer policies](https://developers.google.com/youtube/terms/developer-policies)
- [Pexels API documentation](https://www.pexels.com/api/documentation/)

