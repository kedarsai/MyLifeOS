# LifeOS

Local-first Life OS backend + HTMX UI.

## Quickstart (uv)

```bash
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

## LLM Setup (OpenAI)

Set `OPENAI_API_KEY` in `.env` to enable real OpenAI processing.

```bash
OPENAI_API_KEY=your_key_here
# optional for compatible proxies/self-hosted gateways
OPENAI_BASE_URL=
LIFEOS_MODEL_INGEST=gpt-5-mini
LIFEOS_MODEL_DISTILL=gpt-5-mini
LIFEOS_MODEL_ANALYSIS=gpt-5.2
```

Without a key, the app uses deterministic local fallback logic.

Prompt parameter notes (OpenAI Responses API):
- `gpt-5-mini`: use `verbosity` / `max_output_tokens` and avoid `temperature` / `top_p`.
- `gpt-5.2`: supports `temperature` / `top_p` when `reasoning_effort` is `none`.

You can now update these runtime model settings in the UI at `/prompts` under **LLM Configuration** (optionally persisted to `.env`).

## See UI Output Quickly

1. Open `http://localhost:8000/dashboard` for live summary cards (entries/runs/conflicts).
2. Open `http://localhost:8000/capture` and submit a note.
3. Open `http://localhost:8000/inbox` and click `Process Top 50` (or select specific entries and process).
4. Open `http://localhost:8000/runs` to see logged prompt runs, parse status, output JSON, and errors.
5. Open `http://localhost:8000/timeline` to see processed summaries/tags.

## UI Pages

- `GET /dashboard`
- `GET /goals`
- `GET /today`
- `GET /improvements`
- `GET /chat`
- `GET /reminders`
- `GET /reviews`
- `GET /capture`
- `GET /inbox`
- `GET /timeline`
- `GET /search`
- `GET /conflicts`
- `GET /prompts`
- `GET /runs`

## API

- `GET /api/health`
- `GET /api/dashboard/summary`
- `POST /api/admin/migrate`
- `POST /api/admin/rebuild-index`
- `POST /api/entries/capture`
- `POST /api/entries/capture/batch`
- `GET /api/entries/inbox`
- `POST /api/entries/process-inbox`
- `GET /api/entries/timeline`
- `GET /api/goals`
- `POST /api/goals`
- `GET /api/goals/{goal_id}/dashboard`
- `GET /api/today`
- `POST /api/tasks/{task_id}/complete`
- `GET /api/improvements`
- `POST /api/improvements`
- `PATCH /api/improvements/{improvement_id}/status`
- `GET /api/chat/threads`
- `POST /api/chat/threads`
- `GET /api/chat/threads/{thread_id}/messages`
- `POST /api/chat/threads/{thread_id}/messages`
- `POST /api/chat/threads/{thread_id}/reply`
- `POST /api/chat/threads/{thread_id}/distill`
- `GET /api/chat/context`
- `GET /api/reminders`
- `POST /api/checkin/{kind}`
- `GET /api/backups/status`
- `POST /api/backups/run`
- `GET /api/reviews`
- `POST /api/reviews/generate`
- `GET /api/search`
- `GET /api/conflicts/badge`
- `GET /api/conflicts`
- `GET /api/conflicts/{conflict_id}`
- `POST /api/conflicts/{conflict_id}/resolve`
- `GET /api/prompts`
- `POST /api/prompts/reload`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `POST /api/runs/log`

## Tests

```bash
uv run pytest
```

## Benchmark

```bash
uv run python -m app.tools.generate_search_fixture --db data/lifeos.db --vault Vault --count 5000 --seed 42 --prefix bench --clear-prefix
uv run python -m app.tools.benchmark_search --db data/lifeos.db --vault Vault --storage-label "local-ssd" --query-file docs/benchmark_queries.txt --output-json reports/search_benchmark.json
```
