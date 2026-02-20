from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.db.engine import get_connection
from app.db.migrations import apply_sql_migrations
from app.services.entries import query_entries


def _insert_run(conn, run_id: str) -> None:
    conn.execute(
        """
        INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json, created_at)
        VALUES (?, 'manual', 'test', '{}', '2026-02-19T00:00:00+00:00')
        """,
        (run_id,),
    )


def _insert_entry(
    conn,
    *,
    entry_id: str,
    run_id: str,
    created_at: str,
    entry_type: str,
    status: str,
    tags: list[str],
    goals: list[str],
) -> None:
    conn.execute(
        """
        INSERT INTO entries_index (
          id, path, created_at, updated_at, captured_tz, type, status, summary,
          raw_text, details_md, actions_md, tags_json, goals_json, source_run_id,
          content_hash, content_hash_version
        )
        VALUES (?, ?, ?, ?, 'UTC', ?, ?, ?, ?, '', '', ?, ?, ?, ?, 'sha256-v1')
        """,
        (
            entry_id,
            f"Vault/entries/{entry_id}.md",
            created_at,
            created_at,
            entry_type,
            status,
            f"Summary {entry_id}",
            f"Raw {entry_id}",
            json.dumps(tags),
            json.dumps(goals),
            run_id,
            f"hash-{entry_id}",
        ),
    )


def test_query_entries_inbox_filters_status_and_sorts(tmp_path: Path) -> None:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    apply_sql_migrations(Path.cwd(), settings)

    conn = get_connection(settings)
    try:
        _insert_run(conn, "manual-run-1")
        _insert_run(conn, "manual-run-2")
        _insert_run(conn, "manual-run-3")
        _insert_entry(
            conn,
            entry_id="entry-a",
            run_id="manual-run-1",
            created_at="2026-02-19T10:00:00+00:00",
            entry_type="note",
            status="processed",
            tags=["x"],
            goals=["goal-1"],
        )
        _insert_entry(
            conn,
            entry_id="entry-b",
            run_id="manual-run-2",
            created_at="2026-02-19T12:00:00+00:00",
            entry_type="note",
            status="inbox",
            tags=["x"],
            goals=["goal-1"],
        )
        _insert_entry(
            conn,
            entry_id="entry-c",
            run_id="manual-run-3",
            created_at="2026-02-19T14:00:00+00:00",
            entry_type="idea",
            status="inbox",
            tags=["y"],
            goals=["goal-2"],
        )
        conn.commit()
    finally:
        conn.close()

    result = query_entries(settings, status="inbox", limit=10, offset=0)
    assert result.total == 2
    assert [item["id"] for item in result.items] == ["entry-c", "entry-b"]


def test_query_entries_timeline_filter_combinations(tmp_path: Path) -> None:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    apply_sql_migrations(Path.cwd(), settings)

    conn = get_connection(settings)
    try:
        _insert_run(conn, "manual-run-1")
        _insert_run(conn, "manual-run-2")
        _insert_run(conn, "manual-run-3")
        _insert_entry(
            conn,
            entry_id="entry-a",
            run_id="manual-run-1",
            created_at="2026-02-18T08:00:00+00:00",
            entry_type="note",
            status="processed",
            tags=["focus", "work"],
            goals=["goal-1"],
        )
        _insert_entry(
            conn,
            entry_id="entry-b",
            run_id="manual-run-2",
            created_at="2026-02-19T08:00:00+00:00",
            entry_type="idea",
            status="inbox",
            tags=["focus"],
            goals=["goal-1"],
        )
        _insert_entry(
            conn,
            entry_id="entry-c",
            run_id="manual-run-3",
            created_at="2026-02-20T08:00:00+00:00",
            entry_type="note",
            status="inbox",
            tags=["focus"],
            goals=["goal-2"],
        )
        conn.commit()
    finally:
        conn.close()

    result = query_entries(
        settings,
        entry_type="note",
        tag="focus",
        goal="goal-1",
        date_from="2026-02-17",
        date_to="2026-02-19",
        limit=20,
        offset=0,
    )
    assert result.total == 1
    assert [item["id"] for item in result.items] == ["entry-a"]
