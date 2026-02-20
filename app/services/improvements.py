from __future__ import annotations

import uuid
from typing import Any

from app.core.hashing import PAYLOAD_HASH_VERSION, canonical_payload_hash
from app.core.time import utc_now_iso
from app.db.engine import get_connection


def create_improvement(
    settings,
    *,
    title: str,
    rationale: str,
    source_entry_id: str | None,
    source_run_id: str,
    goal_id: str | None = None,
    status: str = "open",
) -> dict[str, Any]:
    now = utc_now_iso()
    logical_id = f"improvement-{uuid.uuid4()}"
    improvement_id = f"improvement-{uuid.uuid4()}"
    payload_seed = {
        "logical_id": logical_id,
        "title": title,
        "rationale": rationale,
        "goal_id": goal_id,
        "source_entry_id": source_entry_id,
        "status": status,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        safe_goal = None
        if goal_id:
            exists = conn.execute("SELECT 1 FROM goals WHERE goal_id = ?", (goal_id,)).fetchone()
            safe_goal = goal_id if exists else None
        safe_entry = None
        if source_entry_id:
            exists = conn.execute("SELECT 1 FROM entries_index WHERE id = ?", (source_entry_id,)).fetchone()
            safe_entry = source_entry_id if exists else None

        conn.execute(
            """
            INSERT INTO improvements (
              improvement_id, logical_id, path, source_entry_id, source_run_id, goal_id,
              title, rationale, status, last_nudged_at, payload_hash, payload_hash_version,
              version_no, is_current, supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 1, 1, NULL, ?, ?)
            """,
            (
                improvement_id,
                logical_id,
                safe_entry,
                source_run_id,
                safe_goal,
                title.strip(),
                rationale.strip() or "-",
                status,
                payload_hash,
                PAYLOAD_HASH_VERSION,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_improvement(settings, improvement_id)


def list_improvements(settings, *, status: str | None = None, goal_id: str | None = None) -> list[dict[str, Any]]:
    where = "WHERE is_current = 1"
    params: list[Any] = []
    if status:
        where += " AND status = ?"
        params.append(status)
    if goal_id:
        where += " AND goal_id = ?"
        params.append(goal_id)
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            f"""
            SELECT improvement_id, logical_id, source_entry_id, source_run_id, goal_id, title, rationale,
                   status, last_nudged_at, version_no, created_at, updated_at
            FROM improvements
            {where}
            ORDER BY updated_at DESC, improvement_id DESC
            """,
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "improvement_id": row["improvement_id"],
            "logical_id": row["logical_id"],
            "source_entry_id": row["source_entry_id"],
            "source_run_id": row["source_run_id"],
            "goal_id": row["goal_id"],
            "title": row["title"],
            "rationale": row["rationale"],
            "status": row["status"],
            "last_nudged_at": row["last_nudged_at"],
            "version_no": int(row["version_no"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_improvement(settings, improvement_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT improvement_id, logical_id, source_entry_id, source_run_id, goal_id, title, rationale,
                   status, last_nudged_at, version_no, created_at, updated_at
            FROM improvements
            WHERE improvement_id = ?
            """,
            (improvement_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "improvement_id": row["improvement_id"],
        "logical_id": row["logical_id"],
        "source_entry_id": row["source_entry_id"],
        "source_run_id": row["source_run_id"],
        "goal_id": row["goal_id"],
        "title": row["title"],
        "rationale": row["rationale"],
        "status": row["status"],
        "last_nudged_at": row["last_nudged_at"],
        "version_no": int(row["version_no"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def update_improvement_status(settings, improvement_id: str, status: str) -> bool:
    now = utc_now_iso()
    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT 1 FROM improvements WHERE improvement_id = ?",
            (improvement_id,),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE improvements SET status = ?, updated_at = ? WHERE improvement_id = ?",
            (status, now, improvement_id),
        )
        conn.commit()
    finally:
        conn.close()
    return True
