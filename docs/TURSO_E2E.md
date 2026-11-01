# Turso integration verification — 31 October 2026

## Implementation

`trendforge/db.py` uses the official `libsql` driver when Turso credentials are set. The five application tables/indexes are initialized idempotently. Named result rows remain compatible with existing queries, bound parameters are retained, and nested database methods share their caller's transaction. Remote failures return a redacted service error; SQLite is never used as an implicit fallback after a Turso failure. An explicit SQLite override remains available for isolated tests.

Credentials remain backend-only. Connections displays the active database type, without its URL or token. Video files, speech models and encrypted workspace/password configuration remain local.

## Automated checks

- Complete regression suite: **48 passed in 34.69 seconds**, isolated local test data.
- Python compilation and JavaScript syntax passed.
- Driver tests cover named rows, nested rollback, missing configuration, redacted errors and no local fallback.
- Migration utility test checks a local backup, exact project/document/event preservation, refusal to merge a nonempty destination and exclusion of old login sessions.

## Actual frontend → backend → Turso checks

A separate server used port 8767, the real Turso credentials from `.env`, and synthetic local workspace settings under ignored `test-results/turso-browser`. The existing main server on port 8765 was not stopped or reconfigured.

1. Browser sign-in succeeded using a test-only password; sessions used Turso.
2. The browser created a project named `E2E Turso — test only`.
3. Its goal was edited and saved through the browser.
4. An independent `Database` instance connected to Turso and verified the exact persisted value.
5. A stale revision was rejected with HTTP 409.
6. Backend/API brief and posting-caption writes persisted and were verified directly in Turso.
7. Browser reload retained the saved project and updated goal. No browser warnings/errors were observed.
8. An actual remote transaction performed a nested update then raised an intentional exception; a fresh read confirmed rollback.
9. API deletion returned 204; subsequent API read returned 404, and direct remote SQL confirmed all records for the synthetic project were removed from projects/documents/jobs/events.

Screenshot: `docs/screenshots/turso-e2e.png` shows the synthetic project's saved goal after reload. This verifies database connectivity and CRUD; it does not claim a new live AI/YouTube/stock-provider test or a complete remote video render.

## Activation still pending

The main local workspace contains one existing project. Restarting its active service and transferring its records were rejected by automatic approval review because explicit approval was required for stopping the service and exporting existing data. Those operations were not executed. The local project remains in SQLite. The migration utility is prepared and tested; it will back up local data and transfer only projects/documents/jobs/events when authorized. Existing login sessions are excluded and media files stay local.
