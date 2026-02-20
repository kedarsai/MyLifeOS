# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install backend dependencies
uv sync --extra dev

# Run backend server (dev)
uv run uvicorn app.main:app --reload --port 8000

# Run all tests (42 tests)
uv run pytest

# Run a single test file
uv run pytest tests/test_dashboard_api.py -v

# Run a single test function
uv run pytest tests/test_dashboard_api.py::test_dashboard_summary_and_page -v

# Run tests, stop on first failure
uv run pytest -x

# Apply database migrations manually
# POST http://localhost:8000/api/admin/migrate

# Frontend (React SPA)
cd frontend && npm install
cd frontend && npm run dev      # Vite dev server on :5173, proxies /api to :8000
cd frontend && npm run build    # Production build to frontend/dist/
```

### Allowed Tools
- Bash(uv run pytest*)
- Bash(uv run uvicorn*)
- Bash(uv sync*)
- Bash(cd *)
- Bash(cat *)
- Bash(ls *)
- Bash(find *)
- Bash(grep *)
- Bash(mkdir *)
- Bash(npm *)

## Architecture

**Stack**: FastAPI + SQLite (WAL mode) + local markdown vault + React SPA frontend. Two UI layers: legacy HTMX server-rendered pages (`app/ui/`) and a React SPA in `frontend/`.

**Settings** (`app/core/config.py`): Pydantic `BaseSettings` reading from `.env`. Key vars: `LIFEOS_VAULT_PATH` (default `Vault`), `LIFEOS_DB_PATH` (default `data/lifeos.db`), `OPENAI_API_KEY` (required for LLM — without it, deterministic fallbacks are used). Access settings as lowercase: `settings.openai_api_key`, NOT `settings.OPENAI_API_KEY`.

**Startup** (`app/main.py`): The `create_app()` lifespan ensures vault layout, runs SQL migrations, loads default prompt YAML files, and loads prompt templates into the DB. Settings are stored on `app.state.settings` and accessed via `request.app.state.settings` in routes. Also includes SPA catch-all route that serves `frontend/dist/index.html` when the built frontend exists.

### Layer structure

```
app/ui/routes_pages.py    → Legacy HTMX HTML pages (sidebar, nav, layout, all CSS)
app/api/routes_*.py       → API endpoints (JSON + HTML responses)
app/services/*.py         → Business logic, DB queries
app/db/                   → SQLite connection factory, migration runner
app/vault/                → Markdown file I/O, parsing, path generation
frontend/                 → React SPA (Vite + React 19 + TailwindCSS v4 + TanStack Query)
```

Routes are thin — they parse input, call a service function, and format the response. Services own all database and vault operations.

### React SPA frontend (`frontend/`)

Vite + React 19 + TypeScript + TailwindCSS v4 + TanStack React Query. Plane-inspired design: information-dense, 13px base font, dark sidebar, Canvas/Surface/Layer depth system, dark mode first-class.

```
frontend/src/
  api/           → client.ts (fetch wrapper), types.ts, hooks/ (useTasks, useGoals, etc.)
  components/
    ui/          → Button, Badge, Card, Input, Modal, Table, Dropdown, etc.
    layout/      → AppShell, Sidebar, Header, PageHeader
  pages/         → tasks/, goals/, capture/, inbox/, timeline/, dashboard/, today/, etc.
  hooks/         → useTheme, useDebounce
  lib/           → cn.ts, formatters.ts, constants.ts (NAV_GROUPS, ENTRY_TYPES)
  index.css      → Full design token system (CSS custom properties for light/dark)
```

Dev: Vite on `:5173` proxies `/api` to `:8000`. Production: `npm run build` outputs to `frontend/dist/`, FastAPI serves it via catch-all route.

### Dual-response pattern

Every API route supports both JSON and HTML responses using a `_wants_html(request)` check. HTMX requests get HTML fragments; programmatic callers (including the React SPA) get JSON. The check looks at `?format=html` query param, `HX-Request` header, or `Accept` header.

### Form parsing

`app/api/form_utils.py` provides `read_form_body(request)` → `dict[str, list[str]]`, `form_first(data, key)`, and `form_list(data, key)`. Routes that accept both JSON and form data check `content-type` and branch accordingly.

### Vault + Database

Entries are stored as markdown files in `Vault/entries/YYYY/YYYY-MM/` with YAML frontmatter, AND indexed in SQLite (`entries_index` table with FTS). The vault is the source of truth; the DB is a queryable index that can be rebuilt via `POST /api/admin/rebuild-index`.

### Migrations

SQL files in `migrations/` (e.g., `0001_lifeos_v2.sql`). Applied in alphabetical order on startup. Tracked in `schema_migrations` table with SHA256 checksums — modifying an applied migration will error.

### UI page rendering (legacy HTMX)

`app/ui/routes_pages.py` contains `_page(title, body, active, layout)` which wraps page content in the full HTML shell (sidebar, nav, CSS, scripts). Layout modes: `"default"`, `"focused"`, `"split"`, `"wide"`.

## LLM integration

### Models

Configured via environment variables in `app/core/config.py`:
- `LIFEOS_MODEL_INGEST` → `gpt-5-mini` — used for entry extraction and distillation
- `LIFEOS_MODEL_ANALYSIS` → `gpt-5.2` — used for chat responses, chat distillation, weekly reviews

### Prompt pipeline

Prompts are YAML files in `Vault/config/prompts/` loaded into the `prompt_templates` DB table. `app/services/llm.py` renders templates with `{{variable}}` substitution, calls OpenAI with structured output, validates against JSON schemas, and records every call in `prompt_runs`.

**5 prompt configs**: `ingest_extract.yaml`, `distill_outcomes.yaml`, `chat_distill_outcomes.yaml`, `goal_chat_response.yaml`, `weekly_goal_review.yaml`

### Schema locations (CRITICAL)

There are **two copies** of each JSON schema:
- `schemas/*.json` — project root (reference copies)
- `Vault/config/prompts/schemas/*.json` — **runtime source of truth**

The YAML files reference schemas relative to their own directory (e.g., `schema: schemas/ingest_extract.json` resolves to `Vault/config/prompts/schemas/ingest_extract.json`). `load_prompt_templates()` is called on every `process_inbox_entries` and uses `ON CONFLICT DO UPDATE` — meaning the Vault schema **overwrites** any direct DB edits on every call. Always edit the Vault copy.

### OpenAI strict structured output constraints

All schemas must comply with OpenAI's strict mode:
- **ALL** properties must be listed in `required` arrays
- Use `{"type": ["string", "null"]}` for optional/nullable fields (not `oneOf`)
- No `$ref`, `$defs`, `allOf`, `anyOf`, `if/then/not`
- No `format`, `uniqueItems`, `minLength`, `maxLength`, `minItems`, `maxItems`, `minimum`, `maximum`, `exclusiveMinimum`
- `additionalProperties: false` on every object

### Token budget

`gpt-5-mini` uses reasoning tokens that count toward `max_output_tokens`. A simple extraction uses ~900 reasoning + ~290 completion = ~1190 tokens. Current configs: ingest/distill at 2500, chat/reviews at 3000. Do not set below 2000.

### Fallback functions

Every LLM call has a deterministic fallback in the service layer (`entries.py`, `chats.py`, `reviews.py`). Fallback output must include ALL fields required by the schema (use `None` for nullable fields). Key functions:
- `_todo_default_action()`, `_extract_actions_from_md()` in `entries.py`
- `_fallback_chat_response()`, `_fallback_distill_output()` in `chats.py`
- `_build_review_output()` in `reviews.py`

## Test patterns

Tests use `tmp_path` fixtures for full isolation — each test gets its own vault directory and SQLite database:

```python
def test_something(tmp_path: Path) -> None:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    app = create_app()
    app.state.settings = settings
    client = TestClient(app)
    client.post("/api/admin/migrate")
    # ... test logic
```

API tests hit routes via `TestClient`. Service tests call functions directly after setting up the DB with `apply_sql_migrations()` and inserting rows via `conn.execute()`. Tests run without `OPENAI_API_KEY` and exercise deterministic fallback paths.

## Repository

GitHub: `https://github.com/kedarsai/MyLifeOS.git`
