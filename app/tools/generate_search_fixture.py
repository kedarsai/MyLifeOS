from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.db.engine import get_connection
from app.db.migrations import apply_sql_migrations


ENTRY_TYPES = ["note", "idea", "todo", "activity", "chat", "thought"]
TAG_POOL = [
    "focus",
    "sleep",
    "fitness",
    "project",
    "deep-work",
    "review",
    "health",
    "planning",
    "coding",
    "journal",
]
GOAL_POOL = ["goal-1", "goal-2", "goal-3", "goal-4", "goal-5"]
WORD_POOL = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "zenith",
    "focus",
    "sleep",
    "workout",
    "project",
    "review",
    "planning",
    "insight",
    "journal",
    "routine",
    "consistency",
    "nutrition",
]


def _json_dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _build_text(rng: random.Random, min_words: int = 20, max_words: int = 60) -> str:
    count = rng.randint(min_words, max_words)
    words = [rng.choice(WORD_POOL) for _ in range(count)]
    return " ".join(words)


def _rebuild_fts(conn) -> None:
    conn.execute("INSERT INTO fts_entries(fts_entries) VALUES('delete-all')")
    conn.execute("DELETE FROM fts_entries_map")
    rows = conn.execute(
        """
        SELECT id, summary, raw_text, details_md, tags_json, goals_json
        FROM entries_index
        WHERE status != 'archived'
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()

    rowid = 1
    for row in rows:
        conn.execute(
            """
            INSERT INTO fts_entries (rowid, summary, raw_text, details_md, tags, goals)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rowid,
                row["summary"] or "",
                row["raw_text"] or "",
                row["details_md"] or "",
                row["tags_json"] or "[]",
                row["goals_json"] or "[]",
            ),
        )
        conn.execute(
            "INSERT INTO fts_entries_map (entry_id, fts_rowid) VALUES (?, ?)",
            (row["id"], rowid),
        )
        rowid += 1


def generate_search_fixture(
    settings: Settings,
    *,
    count: int,
    seed: int = 42,
    prefix: str = "bench",
    clear_existing_prefix: bool = False,
) -> dict[str, int]:
    if count < 1:
        raise ValueError("count must be >= 1")

    apply_sql_migrations(Path.cwd(), settings)
    rng = random.Random(seed)
    run_id = f"{prefix}-run-{seed}"
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    conn = get_connection(settings)
    try:
        conn.execute(
            """
            INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json, created_at)
            VALUES (?, 'import', 'fixture', ?, datetime('now'))
            ON CONFLICT(run_id) DO NOTHING
            """,
            (run_id, _json_dump({"tool": "generate_search_fixture"})),
        )

        if clear_existing_prefix:
            like_expr = f"{prefix}-%"
            conn.execute("DELETE FROM entries_index WHERE id LIKE ?", (like_expr,))

        batch = []
        for i in range(int(count)):
            entry_id = f"{prefix}-{seed}-{i:06d}"
            created_dt = start + timedelta(minutes=i)
            created_iso = created_dt.replace(microsecond=0).isoformat()
            entry_type = rng.choice(ENTRY_TYPES)
            status = "processed" if i % 5 else "inbox"
            tags = rng.sample(TAG_POOL, k=rng.randint(1, 3))
            goals = rng.sample(GOAL_POOL, k=rng.randint(0, 2))
            summary = _build_text(rng, 5, 10)
            raw_text = _build_text(rng, 30, 80)
            details_md = _build_text(rng, 10, 20)
            actions_md = "- [ ] " + _build_text(rng, 4, 8)
            batch.append(
                (
                    entry_id,
                    f"{settings.vault_path.as_posix()}/entries/fixture/{entry_id}.md",
                    created_iso,
                    created_iso,
                    "UTC",
                    entry_type,
                    status,
                    summary,
                    raw_text,
                    details_md,
                    actions_md,
                    _json_dump(tags),
                    _json_dump(goals),
                    run_id,
                    f"{prefix}-hash-{seed}-{i:06d}",
                    "sha256-v1",
                )
            )

            if len(batch) >= 1000:
                conn.executemany(
                    """
                    INSERT INTO entries_index (
                      id, path, created_at, updated_at, captured_tz, type, status, summary,
                      raw_text, details_md, actions_md, tags_json, goals_json, source_run_id,
                      content_hash, content_hash_version
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      path=excluded.path,
                      created_at=excluded.created_at,
                      updated_at=excluded.updated_at,
                      captured_tz=excluded.captured_tz,
                      type=excluded.type,
                      status=excluded.status,
                      summary=excluded.summary,
                      raw_text=excluded.raw_text,
                      details_md=excluded.details_md,
                      actions_md=excluded.actions_md,
                      tags_json=excluded.tags_json,
                      goals_json=excluded.goals_json,
                      source_run_id=excluded.source_run_id,
                      content_hash=excluded.content_hash,
                      content_hash_version=excluded.content_hash_version
                    """,
                    batch,
                )
                batch = []

        if batch:
            conn.executemany(
                """
                INSERT INTO entries_index (
                  id, path, created_at, updated_at, captured_tz, type, status, summary,
                  raw_text, details_md, actions_md, tags_json, goals_json, source_run_id,
                  content_hash, content_hash_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  path=excluded.path,
                  created_at=excluded.created_at,
                  updated_at=excluded.updated_at,
                  captured_tz=excluded.captured_tz,
                  type=excluded.type,
                  status=excluded.status,
                  summary=excluded.summary,
                  raw_text=excluded.raw_text,
                  details_md=excluded.details_md,
                  actions_md=excluded.actions_md,
                  tags_json=excluded.tags_json,
                  goals_json=excluded.goals_json,
                  source_run_id=excluded.source_run_id,
                  content_hash=excluded.content_hash,
                  content_hash_version=excluded.content_hash_version
                """,
                batch,
            )

        _rebuild_fts(conn)
        conn.commit()

        total_entries = conn.execute("SELECT COUNT(*) AS c FROM entries_index").fetchone()["c"]
        total_fts = conn.execute("SELECT COUNT(*) AS c FROM fts_entries_map").fetchone()["c"]
    finally:
        conn.close()

    return {
        "inserted_or_updated": int(count),
        "total_entries": int(total_entries),
        "total_fts_rows": int(total_fts),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate reproducible search benchmark fixture.")
    parser.add_argument("--db", required=True, help="Path to sqlite db")
    parser.add_argument("--vault", required=True, help="Path to vault root")
    parser.add_argument("--count", type=int, default=5000, help="Number of entries to generate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prefix", default="bench")
    parser.add_argument(
        "--clear-prefix",
        action="store_true",
        help="Delete rows with ids matching <prefix>-% before generation",
    )
    args = parser.parse_args()

    settings = Settings(
        LIFEOS_DB_PATH=str(Path(args.db)),
        LIFEOS_VAULT_PATH=str(Path(args.vault)),
        LIFEOS_TIMEZONE="UTC",
    )
    out = generate_search_fixture(
        settings,
        count=args.count,
        seed=args.seed,
        prefix=args.prefix,
        clear_existing_prefix=args.clear_prefix,
    )
    print(
        "Generated fixture:"
        f" inserted_or_updated={out['inserted_or_updated']}"
        f" total_entries={out['total_entries']}"
        f" total_fts_rows={out['total_fts_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
