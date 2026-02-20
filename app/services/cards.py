from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.hashing import PAYLOAD_HASH_VERSION, canonical_payload_hash
from app.core.time import utc_now_iso
from app.db.engine import get_connection


_ENTITY_TYPES = {"goal", "thought_topic", "idea"}


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


def save_card(
    settings,
    *,
    entity_type: str,
    entity_id: str,
    title: str,
    body_md: str,
    source_run_id: str,
    action_taken: str | None = None,
    source_thread_id: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    if entity_type not in _ENTITY_TYPES:
        raise ValueError(f"Invalid entity_type: {entity_type}")

    now = utc_now_iso()
    logical_id = f"card-{uuid.uuid4()}"
    card_id = f"card-{uuid.uuid4()}"
    tags_list = tags or []
    payload_seed = {
        "logical_id": logical_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "title": title,
        "body_md": body_md,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        _ensure_run(conn, source_run_id)
        conn.execute(
            """
            INSERT INTO insight_cards (
              card_id, logical_id, source_run_id, entity_type, entity_id,
              source_thread_id, title, body_md, action_taken, tags_json,
              payload_hash, payload_hash_version, version_no, is_current,
              supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, NULL, ?, ?)
            """,
            (
                card_id, logical_id, source_run_id, entity_type, entity_id,
                source_thread_id, title.strip(), body_md.strip(),
                action_taken, _json_dump(tags_list),
                payload_hash, PAYLOAD_HASH_VERSION,
                now, now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_card(settings, card_id)


def get_card(settings, card_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT card_id, logical_id, source_run_id, entity_type, entity_id,
                   source_thread_id, title, body_md, action_taken, tags_json,
                   version_no, is_current, created_at, updated_at
            FROM insight_cards
            WHERE card_id = ?
            """,
            (card_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return _row_to_dict(row)


def list_cards(
    settings,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    q: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    where = "WHERE is_current = 1"
    params: list[Any] = []
    if entity_type:
        where += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        where += " AND entity_id = ?"
        params.append(entity_id)
    if q:
        where += " AND (title LIKE ? OR body_md LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])
    params.append(int(limit))
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            f"""
            SELECT card_id, logical_id, source_run_id, entity_type, entity_id,
                   source_thread_id, title, body_md, action_taken, tags_json,
                   version_no, is_current, created_at, updated_at
            FROM insight_cards
            {where}
            ORDER BY created_at DESC, card_id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(row) for row in rows]


def cards_for_context(
    settings,
    *,
    entity_type: str,
    entity_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT card_id, title, body_md, tags_json, created_at
            FROM insight_cards
            WHERE is_current = 1 AND entity_type = ? AND entity_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (entity_type, entity_id, int(limit)),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "card_id": row["card_id"],
            "title": row["title"],
            "body_md": row["body_md"][:500],
            "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "card_id": row["card_id"],
        "logical_id": row["logical_id"],
        "source_run_id": row["source_run_id"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "source_thread_id": row["source_thread_id"],
        "title": row["title"],
        "body_md": row["body_md"],
        "action_taken": row["action_taken"],
        "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
        "version_no": int(row["version_no"]),
        "is_current": bool(row["is_current"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
