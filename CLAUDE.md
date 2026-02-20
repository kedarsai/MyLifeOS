# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync --extra dev

# Run server (dev)
uv run uvicorn app.main:app --reload --port 8000

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_dashboard_api.py -v

# Run a single test function
uv run pytest tests/test_dashboard_api.py::test_dashboard_summary_and_page -v

# Run tests, stop on first failure
uv run pytest -x

# Apply database migrations manually
# POST http://localhost:8000/api/admin/migrate
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

## Architecture

**Stack**: FastAPI + HTMX + SQLite (WAL mode) + local markdown vault. No frontend build step — all UI is server-rendered HTML with HTMX for dynamic updates.

**Settings** (`app/core/config.py`): Pydantic `BaseSettings` reading from `.env`. Key vars: `LIFEOS_VAULT_PATH` (default `Vault`), `LIFEOS_DB_PATH` (default `data/lifeos.db`), `OPENAI_API_KEY` (optional — without it, LLM calls use deterministic fallback logic).

**Startup** (`app/main.py`): The `create_app()` lifespan ensures vault layout, runs SQL migrations, loads default prompt YAML files, and loads prompt templates into the DB. Settings are stored on `app.state.settings` and accessed via `request.app.state.settings` in routes.

### Layer structure

```
app/ui/routes_pages.py    → Full HTML pages (sidebar, nav, layout, all CSS)
app/api/routes_*.py       → API endpoints (JSON + HTML responses)
app/services/*.py         → Business logic, DB queries
app/db/                   → SQLite connection factory, migration runner
app/vault/                → Markdown file I/O, parsing, path generation
```

Routes are thin — they parse input, call a service function, and format the response. Services own all database and vault operations.

### Dual-response pattern

Every API route supports both JSON and HTML responses using a `_wants_html(request)` check. HTMX requests get HTML fragments; programmatic callers get JSON. The check looks at `?format=html` query param, `HX-Request` header, or `Accept` header.

```python
if _wants_html(request):
    return HTMLResponse(_render_something(data))
return data  # JSON
```

### Form parsing

`app/api/form_utils.py` provides `read_form_body(request)` → `dict[str, list[str]]`, `form_first(data, key)`, and `form_list(data, key)`. Routes that accept both JSON and form data check `content-type` and branch accordingly.

### Vault + Database

Entries are stored as markdown files in `Vault/entries/YYYY/YYYY-MM/` with YAML frontmatter, AND indexed in SQLite (`entries_index` table with FTS). The vault is the source of truth; the DB is a queryable index that can be rebuilt via `POST /api/admin/rebuild-index`.

### Migrations

SQL files in `migrations/` (e.g., `0001_lifeos_v2.sql`). Applied in alphabetical order on startup. Tracked in `schema_migrations` table with SHA256 checksums — modifying an applied migration will error.

### UI page rendering

`app/ui/routes_pages.py` contains `_page(title, body, active, layout)` which wraps page content in the full HTML shell (sidebar, nav, CSS, scripts). Layout modes: `"default"`, `"focused"` (auto-collapsed sidebar, centered 960px), `"split"` (340px+1fr two-column), `"wide"` (full width). Workflow bars (`_workflow_bar()`) connect related pages visually.





### LLM integration

Prompts are YAML files in `Vault/config/prompts/` loaded into the `prompt_templates` DB table. `app/services/llm.py` renders templates with `{{variable}}` substitution, calls OpenAI, validates output against JSON schemas in `schemas/`, and records every call in `prompt_runs`. All LLM-dependent code paths have deterministic fallbacks for when no API key is set.

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

API tests hit routes via `TestClient`. Service tests call functions directly after setting up the DB with `apply_sql_migrations()` and inserting rows via `conn.execute()`.
