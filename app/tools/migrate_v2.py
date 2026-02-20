from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


VERSIONED_TABLES = [
    ("entry_versions", "version_id"),
    ("obs_activity", "observation_id"),
    ("obs_sleep", "observation_id"),
    ("obs_food", "observation_id"),
    ("obs_weight", "observation_id"),
    ("tasks", "task_id"),
    ("improvements", "improvement_id"),
    ("insights", "insight_id"),
    ("chat_threads", "thread_id"),
]

SOURCE_RUN_TABLES = [
    ("entries_index", "id"),
    ("entry_versions", "version_id"),
    ("obs_activity", "observation_id"),
    ("obs_sleep", "observation_id"),
    ("obs_food", "observation_id"),
    ("obs_weight", "observation_id"),
    ("tasks", "task_id"),
    ("improvements", "improvement_id"),
    ("insights", "insight_id"),
    ("chat_threads", "thread_id"),
    ("chat_messages", "message_id"),
    ("weekly_reviews", "review_id"),
]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute(
        """
        INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json)
        VALUES (?, 'import', 'migration', '{}')
        ON CONFLICT(run_id) DO NOTHING
        """,
        (run_id,),
    )


def _fill_missing_source_runs(conn: sqlite3.Connection, apply: bool) -> int:
    fixes = 0
    for table, id_col in SOURCE_RUN_TABLES:
        if not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        if "source_run_id" not in cols:
            continue
        rows = conn.execute(
            f"""
            SELECT {id_col}
            FROM {table}
            WHERE source_run_id IS NULL OR TRIM(source_run_id) = ''
            """
        ).fetchall()
        for row in rows:
            pk = str(row[0])
            run_id = f"mig-v2-{table}-{pk}"
            fixes += 1
            if apply:
                _ensure_run(conn, run_id)
                conn.execute(
                    f"UPDATE {table} SET source_run_id = ? WHERE {id_col} = ?",
                    (run_id, pk),
                )
    return fixes


def _backfill_logical_ids(conn: sqlite3.Connection, apply: bool) -> int:
    fixes = 0
    for table, id_col in VERSIONED_TABLES:
        if not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        if "logical_id" not in cols:
            continue
        rows = conn.execute(
            f"""
            SELECT {id_col}
            FROM {table}
            WHERE logical_id IS NULL OR TRIM(logical_id) = ''
            """
        ).fetchall()
        fixes += len(rows)
        if apply and rows:
            conn.execute(
                f"""
                UPDATE {table}
                SET logical_id = {id_col}
                WHERE logical_id IS NULL OR TRIM(logical_id) = ''
                """
            )
    return fixes


def _recompute_versions(conn: sqlite3.Connection, apply: bool) -> int:
    touched = 0
    for table, _ in VERSIONED_TABLES:
        if not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        required = {"logical_id", "version_no", "is_current"}
        if not required.issubset(cols):
            continue

        count = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE logical_id IS NOT NULL AND TRIM(logical_id) != ''"
        ).fetchone()[0]
        touched += int(count)
        if not apply or count == 0:
            continue

        created_col = "created_at" if "created_at" in cols else "rowid"
        updated_col = "updated_at" if "updated_at" in cols else created_col

        conn.execute(
            f"""
            WITH ranked AS (
              SELECT
                rowid AS rid,
                logical_id,
                ROW_NUMBER() OVER (
                  PARTITION BY logical_id
                  ORDER BY COALESCE({created_col}, ''), rowid
                ) AS rn,
                ROW_NUMBER() OVER (
                  PARTITION BY logical_id
                  ORDER BY COALESCE({updated_col}, COALESCE({created_col}, '')) DESC, rowid DESC
                ) AS cur_rank
              FROM {table}
              WHERE logical_id IS NOT NULL AND TRIM(logical_id) != ''
            )
            UPDATE {table}
            SET
              version_no = (SELECT rn FROM ranked WHERE ranked.rid = {table}.rowid),
              is_current = CASE
                WHEN (SELECT cur_rank FROM ranked WHERE ranked.rid = {table}.rowid) = 1 THEN 1
                ELSE 0
              END
            WHERE rowid IN (SELECT rid FROM ranked)
            """
        )
    return touched


def _verify_invariants(conn: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    for table, _ in SOURCE_RUN_TABLES:
        if not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        if "source_run_id" not in cols:
            continue
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE source_run_id IS NULL OR TRIM(source_run_id) = ''"
        ).fetchone()[0]
        if count:
            errors.append(f"{table}: {count} rows with missing source_run_id")

    for table, _ in VERSIONED_TABLES:
        if not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        if not {"logical_id", "is_current"}.issubset(cols):
            continue
        bad = conn.execute(
            f"""
            SELECT COUNT(*) FROM (
              SELECT logical_id, SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END) AS c
              FROM {table}
              GROUP BY logical_id
              HAVING c != 1
            )
            """
        ).fetchone()[0]
        if bad:
            errors.append(f"{table}: {bad} logical chains with current_count != 1")
    return errors


def run(db_path: Path, apply: bool) -> int:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if not _table_exists(conn, "artifact_runs"):
            print("artifact_runs table is missing; apply base migrations first.")
            return 2

        if apply:
            conn.execute("BEGIN")
        missing_runs = _fill_missing_source_runs(conn, apply)
        backfilled_logical = _backfill_logical_ids(conn, apply)
        touched_versions = _recompute_versions(conn, apply)

        if apply:
            conn.commit()

        errors = _verify_invariants(conn)
        print(f"source_run_id fixes: {missing_runs}")
        print(f"logical_id backfills: {backfilled_logical}")
        print(f"version rows recomputed: {touched_versions}")
        if errors:
            print("invariant errors:")
            for err in errors:
                print(f"- {err}")
            return 1
        print("migration verification passed")
        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill pre-v2 LifeOS DB data.")
    parser.add_argument("--db", required=True, type=Path, help="Path to sqlite db")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag, runs in dry-run analysis mode.",
    )
    args = parser.parse_args()
    return run(args.db, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
