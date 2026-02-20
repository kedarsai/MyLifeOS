from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.time import utc_now_iso
from app.db.engine import get_connection


def _json_dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _ensure_run(conn, run_id: str) -> None:
    conn.execute(
        """
        INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json, created_at)
        VALUES (?, 'system', 'local_user', '{}', ?)
        ON CONFLICT(run_id) DO NOTHING
        """,
        (run_id, utc_now_iso()),
    )


def get_or_create_area(
    settings,
    *,
    name: str,
    source_run_id: str,
    description: str = "",
) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Area name must not be empty.")
    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT area_id, name, description, source_run_id, created_at, updated_at "
            "FROM thought_areas WHERE name = ? COLLATE NOCASE",
            (clean_name,),
        ).fetchone()
        if row:
            return {
                "area_id": row["area_id"],
                "name": row["name"],
                "description": row["description"],
                "source_run_id": row["source_run_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        now = utc_now_iso()
        area_id = f"area-{uuid.uuid4()}"
        _ensure_run(conn, source_run_id)
        conn.execute(
            """
            INSERT INTO thought_areas (area_id, name, description, source_run_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (area_id, clean_name, description.strip(), source_run_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return get_area(settings, area_id)


def get_area(settings, area_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT area_id, name, description, source_run_id, created_at, updated_at "
            "FROM thought_areas WHERE area_id = ?",
            (area_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "area_id": row["area_id"],
        "name": row["name"],
        "description": row["description"],
        "source_run_id": row["source_run_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_or_create_topic(
    settings,
    *,
    area_id: str,
    name: str,
    source_run_id: str,
    description: str = "",
) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Topic name must not be empty.")
    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT topic_id, area_id, name, description, source_run_id, created_at, updated_at "
            "FROM thought_topics WHERE area_id = ? AND name = ? COLLATE NOCASE",
            (area_id, clean_name),
        ).fetchone()
        if row:
            return {
                "topic_id": row["topic_id"],
                "area_id": row["area_id"],
                "name": row["name"],
                "description": row["description"],
                "source_run_id": row["source_run_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        now = utc_now_iso()
        topic_id = f"topic-{uuid.uuid4()}"
        _ensure_run(conn, source_run_id)
        conn.execute(
            """
            INSERT INTO thought_topics (topic_id, area_id, name, description, source_run_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (topic_id, area_id, clean_name, description.strip(), source_run_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return get_topic(settings, topic_id)


def get_topic(settings, topic_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT topic_id, area_id, name, description, source_run_id, created_at, updated_at "
            "FROM thought_topics WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "topic_id": row["topic_id"],
        "area_id": row["area_id"],
        "name": row["name"],
        "description": row["description"],
        "source_run_id": row["source_run_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def assign_entry_topic(
    settings,
    *,
    entry_id: str,
    topic_id: str,
    source_run_id: str,
) -> bool:
    conn = get_connection(settings)
    try:
        _ensure_run(conn, source_run_id)
        conn.execute(
            """
            INSERT INTO entry_topics (entry_id, topic_id, source_run_id, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(entry_id, topic_id) DO NOTHING
            """,
            (entry_id, topic_id, source_run_id, utc_now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def process_topic_assignments(
    settings,
    *,
    entry_id: str,
    source_run_id: str,
    assignments: list[dict[str, Any]],
) -> list[str]:
    topic_ids: list[str] = []
    for item in assignments:
        if not isinstance(item, dict):
            continue
        area_name = str(item.get("area_name") or "").strip()
        topic_name = str(item.get("topic_name") or "").strip()
        if not area_name or not topic_name:
            continue
        area = get_or_create_area(settings, name=area_name, source_run_id=source_run_id)
        topic = get_or_create_topic(
            settings, area_id=area["area_id"], name=topic_name, source_run_id=source_run_id,
        )
        assign_entry_topic(settings, entry_id=entry_id, topic_id=topic["topic_id"], source_run_id=source_run_id)
        topic_ids.append(topic["topic_id"])
    return topic_ids


def list_areas(settings) -> list[dict[str, Any]]:
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT a.area_id, a.name, a.description, a.created_at, a.updated_at,
                   COUNT(t.topic_id) AS topic_count
            FROM thought_areas a
            LEFT JOIN thought_topics t ON t.area_id = a.area_id
            GROUP BY a.area_id
            ORDER BY a.name COLLATE NOCASE
            """,
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "area_id": row["area_id"],
            "name": row["name"],
            "description": row["description"],
            "topic_count": int(row["topic_count"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def list_topics(settings, *, area_id: str) -> list[dict[str, Any]]:
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT t.topic_id, t.area_id, t.name, t.description, t.created_at, t.updated_at,
                   COUNT(et.entry_id) AS entry_count
            FROM thought_topics t
            LEFT JOIN entry_topics et ON et.topic_id = t.topic_id
            WHERE t.area_id = ?
            GROUP BY t.topic_id
            ORDER BY t.name COLLATE NOCASE
            """,
            (area_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "topic_id": row["topic_id"],
            "area_id": row["area_id"],
            "name": row["name"],
            "description": row["description"],
            "entry_count": int(row["entry_count"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_topic_detail(settings, topic_id: str) -> dict[str, Any] | None:
    topic = get_topic(settings, topic_id)
    if not topic:
        return None
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT e.id, e.summary, e.type, e.created_at, e.tags_json
            FROM entries_index e
            JOIN entry_topics et ON et.entry_id = e.id
            WHERE et.topic_id = ?
            ORDER BY e.created_at DESC
            LIMIT 50
            """,
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()
    entries = [
        {
            "id": row["id"],
            "summary": row["summary"] or "",
            "type": row["type"],
            "created_at": row["created_at"],
            "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
        }
        for row in rows
    ]
    return {**topic, "entries": entries}


def attention_heatmap(settings, *, months: int = 6) -> list[dict[str, Any]]:
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT a.area_id, a.name AS area_name,
                   strftime('%Y-%m', e.created_at) AS month,
                   COUNT(DISTINCT et.entry_id) AS entry_count
            FROM thought_areas a
            JOIN thought_topics t ON t.area_id = a.area_id
            JOIN entry_topics et ON et.topic_id = t.topic_id
            JOIN entries_index e ON e.id = et.entry_id
            WHERE e.created_at >= date('now', ? || ' months')
            GROUP BY a.area_id, month
            ORDER BY month DESC, a.name COLLATE NOCASE
            """,
            (f"-{months}",),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "area_id": row["area_id"],
            "area_name": row["area_name"],
            "month": row["month"],
            "entry_count": int(row["entry_count"]),
        }
        for row in rows
    ]


def topics_context(settings) -> list[dict[str, Any]]:
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT a.name AS area_name, t.name AS topic_name
            FROM thought_areas a
            JOIN thought_topics t ON t.area_id = a.area_id
            ORDER BY a.name COLLATE NOCASE, t.name COLLATE NOCASE
            """,
        ).fetchall()
    finally:
        conn.close()
    return [{"area": row["area_name"], "topic": row["topic_name"]} for row in rows]
