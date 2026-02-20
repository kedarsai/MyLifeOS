# LifeOS Implementation Status

Last updated: 2026-02-19

## Delivery State
- Package/tooling: `uv`
- Architecture: API-first (FastAPI + HTMX pages)
- Data model: SQLite + local markdown vault
- Delivery scope now: Epics 1 through 10 implemented at V2 level

## Epic Completion Snapshot

## Epic 1 Foundation
- Vault manager, markdown parser/writer, SQL migrations, rebuild indexer, hashing utilities.
- Rebuild now covers entries, goals, tasks, improvements, insights, chats, and weekly reviews.

## Epic 2 Capture + Inbox + Timeline + Conflicts
- Capture single/batch, inbox queue, process-inbox, timeline filters/pagination.
- Conflict center queue/detail/resolve + global conflict badge.
- Form and JSON input paths supported.

## Epic 3 Search
- FTS-backed search API + UI with facets, snippets, pagination.
- Benchmark tools + fixtures for repeatable latency checks (5k and 50k).

## Epic 4 Prompt Registry + Run Logging
- Prompt YAML registry loader and reload endpoint.
- Prompt run logging with schema validation.
- Retry/replay endpoint for failed runs.
- Default prompt assets provisioned at startup.

## Epic 5 Ingestion/Extraction
- OpenAI-backed ingestion (`ingest_extract@v1`) integrated via official OpenAI SDK.
- Deterministic fallback remains active when `OPENAI_API_KEY` is not set or schema parse fails.
- Observation extraction now maps to:
  - `obs_activity`
  - `obs_sleep`
  - `obs_food`
  - `obs_weight`
- Batch processing is resilient (failed schema rows do not block other rows).

## Epic 6 Goals
- Goal CRUD, entry linking, deterministic goal dashboard metrics.
- Dashboard now includes latest weekly review summary when available.

## Epic 7 Todos + Improvements
- Task extraction/sync from markdown checkbox actions.
- Today endpoint/page with due/overdue/next-action buckets + quick complete.
- Improvements CRUD/status tracking in API/UI.

## Epic 8 Goal Chat + Distill Outcomes
- Chat thread/message persistence in DB + vault transcript notes.
- Goal context builder (goal rules, metrics, recent linked entries).
- OpenAI-backed goal reply generation (`goal_chat_response@v1`) added:
  - `POST /api/chat/threads/{thread_id}/reply`
- OpenAI-backed distill outcomes (`chat_distill_outcomes@v1`) creates insights/improvements/tasks.
- Deterministic fallback remains active for chat/distill when LLM is unavailable.

## Epic 9 Missing Data + Reminders
- Missing-log detector and reminders summary.
- Quick check-in endpoints/forms for sleep/food/activity.
- Check-ins support explicit backfill date and immediate inbox processing.
- Backup endpoints:
  - `GET /api/backups/status`
  - `POST /api/backups/run` (`hourly|daily`)

## Epic 10 Weekly Review
- Weekly review generation now uses OpenAI (`weekly_goal_review@v1`) with deterministic fallback.
- Schema validation against `weekly_goal_review@v1`.
- Prompt run logging for weekly reviews.
- Markdown review artifact written to `Vault/reviews/`.
- API + UI added:
  - `POST /api/reviews/generate`
  - `GET /api/reviews`
  - `GET /reviews`

## UI State
- Responsive sidebar shell with pages:
  - `/dashboard`, `/goals`, `/today`, `/improvements`, `/chat`, `/reminders`, `/reviews`
  - `/capture`, `/inbox`, `/timeline`, `/search`, `/prompts`, `/runs`, `/conflicts`

## Validation
- Test suite: `uv run pytest -q` -> `28 passed`
- Local smoke on alternate port:
  - `http://127.0.0.1:8012/api/health` -> 200
  - `http://127.0.0.1:8012/dashboard` -> 200
  - `http://127.0.0.1:8012/tasks` -> 200
  - `http://127.0.0.1:8012/projects` -> 200
  - `http://127.0.0.1:8012/search` -> 200
  - `http://127.0.0.1:8012/api/chat/threads/{id}/reply` -> working

## Run Commands
- Sync deps: `uv sync --extra dev`
- Tests: `uv run pytest -q`
- Start app: `uv run uvicorn app.main:app --reload --port 8000`
