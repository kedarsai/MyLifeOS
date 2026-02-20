from pathlib import Path

from app.core.config import Settings
from app.db.engine import get_connection
from app.db.migrations import apply_sql_migrations
from app.services.indexer import VaultIndexer


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_rebuild_indexes_entries_and_tasks(tmp_path: Path) -> None:
    vault = tmp_path / "Vault"
    db_path = tmp_path / "data" / "lifeos.db"

    entry_md = """---
id: entry-1
created: 2026-02-19T18:05:00+00:00
type: note
status: inbox
goals: [goal-1]
tags: [capture]
summary: "Quick note"
source_run_id: manual-run-1
---

## Details
- first detail

## Actions
- [ ] first action

## Context (Raw)
Original raw text.
"""
    task_md = """---
id: task-1
logical_id: task-1
entity_type: task
goal_id: goal-1
source_entry_id: entry-1
source_run_id: manual-run-2
version_no: 1
is_current: true
supersedes_id: null
status: open
priority: medium
due_date: null
created: 2026-02-19T18:10:00+00:00
updated: 2026-02-19T18:10:00+00:00
---

## Title
Walk after lunch

## Rationale
Improve daily consistency
"""
    _write(vault / "entries/2026/2026-02/2026-02-19_18-05_note_quick-note.md", entry_md)
    _write(vault / "tasks/task-1_walk-after-lunch.md", task_md)

    settings = Settings(
        LIFEOS_VAULT_PATH=str(vault),
        LIFEOS_DB_PATH=str(db_path),
        LIFEOS_TIMEZONE="UTC",
    )
    apply_sql_migrations(Path.cwd(), settings)
    stats = VaultIndexer(settings).rebuild()
    assert stats.entries_indexed == 1
    assert stats.tasks_indexed == 1

    conn = get_connection(settings)
    try:
        entry_count = conn.execute("SELECT COUNT(*) AS c FROM entries_index").fetchone()["c"]
        task_count = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()["c"]
        run_count = conn.execute("SELECT COUNT(*) AS c FROM artifact_runs").fetchone()["c"]
        assert entry_count == 1
        assert task_count == 1
        assert run_count >= 2
    finally:
        conn.close()

