from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.hashing import PAYLOAD_HASH_VERSION, canonical_payload_hash
from app.core.time import utc_now_iso
from app.db.engine import get_connection


_IDEA_STATUSES = {"raw", "exploring", "mature", "converted", "parked", "dropped"}
_CONVERT_TARGETS = {"goal", "project", "task"}


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


def create_idea(
    settings,
    *,
    title: str,
    description: str = "",
    source_entry_id: str | None = None,
    source_run_id: str,
    status: str = "raw",
) -> dict[str, Any]:
    now = utc_now_iso()
    logical_id = f"idea-{uuid.uuid4()}"
    idea_id = f"idea-{uuid.uuid4()}"
    payload_seed = {
        "logical_id": logical_id,
        "title": title,
        "description": description,
        "source_entry_id": source_entry_id,
        "status": status,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        safe_entry = None
        if source_entry_id:
            exists = conn.execute(
                "SELECT 1 FROM entries_index WHERE id = ?", (source_entry_id,),
            ).fetchone()
            safe_entry = source_entry_id if exists else None

        _ensure_run(conn, source_run_id)
        conn.execute(
            """
            INSERT INTO ideas (
              idea_id, logical_id, title, description, status,
              converted_to_type, converted_to_id, source_entry_id, source_run_id,
              payload_hash, payload_hash_version, version_no, is_current,
              supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, 1, 1, NULL, ?, ?)
            """,
            (
                idea_id, logical_id, title.strip(), description.strip(),
                status if status in _IDEA_STATUSES else "raw",
                safe_entry, source_run_id,
                payload_hash, PAYLOAD_HASH_VERSION,
                now, now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_idea(settings, idea_id)


def get_idea(settings, idea_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT idea_id, logical_id, title, description, status,
                   converted_to_type, converted_to_id, source_entry_id, source_run_id,
                   version_no, is_current, created_at, updated_at
            FROM ideas
            WHERE idea_id = ?
            """,
            (idea_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "idea_id": row["idea_id"],
        "logical_id": row["logical_id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "converted_to_type": row["converted_to_type"],
        "converted_to_id": row["converted_to_id"],
        "source_entry_id": row["source_entry_id"],
        "source_run_id": row["source_run_id"],
        "version_no": int(row["version_no"]),
        "is_current": bool(row["is_current"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def link_entry_to_idea(
    settings,
    *,
    idea_id: str,
    entry_id: str,
    link_type: str = "related",
    source_run_id: str,
) -> bool:
    conn = get_connection(settings)
    try:
        _ensure_run(conn, source_run_id)
        conn.execute(
            """
            INSERT INTO idea_entries (idea_id, entry_id, link_type, source_run_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(idea_id, entry_id, link_type) DO NOTHING
            """,
            (idea_id, entry_id, link_type, source_run_id, utc_now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def process_idea_links(
    settings,
    *,
    entry_id: str,
    source_run_id: str,
    links: list[dict[str, Any]],
) -> list[str]:
    idea_ids: list[str] = []
    for item in links:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "").strip()
        if mode == "new":
            new_title = str(item.get("new_title") or "").strip()
            if not new_title:
                continue
            new_desc = str(item.get("new_description") or "").strip()
            idea = create_idea(
                settings,
                title=new_title,
                description=new_desc,
                source_entry_id=entry_id,
                source_run_id=source_run_id,
            )
            link_entry_to_idea(
                settings,
                idea_id=idea["idea_id"],
                entry_id=entry_id,
                link_type="source",
                source_run_id=source_run_id,
            )
            idea_ids.append(idea["idea_id"])
        elif mode == "existing":
            existing_id = str(item.get("idea_id") or "").strip()
            if not existing_id:
                continue
            existing = get_idea(settings, existing_id)
            if not existing:
                continue
            link_entry_to_idea(
                settings,
                idea_id=existing_id,
                entry_id=entry_id,
                link_type="related",
                source_run_id=source_run_id,
            )
            idea_ids.append(existing_id)
    return idea_ids


def list_ideas(
    settings,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    where = "WHERE is_current = 1"
    params: list[Any] = []
    if status and status in _IDEA_STATUSES:
        where += " AND status = ?"
        params.append(status)
    params.append(int(limit))
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            f"""
            SELECT i.idea_id, i.logical_id, i.title, i.description, i.status,
                   i.converted_to_type, i.converted_to_id, i.source_entry_id,
                   i.version_no, i.created_at, i.updated_at,
                   COUNT(ie.entry_id) AS entry_count
            FROM ideas i
            LEFT JOIN idea_entries ie ON ie.idea_id = i.idea_id
            {where}
            GROUP BY i.idea_id
            ORDER BY i.updated_at DESC, i.idea_id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "idea_id": row["idea_id"],
            "logical_id": row["logical_id"],
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "converted_to_type": row["converted_to_type"],
            "converted_to_id": row["converted_to_id"],
            "source_entry_id": row["source_entry_id"],
            "entry_count": int(row["entry_count"]),
            "version_no": int(row["version_no"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_idea_detail(settings, idea_id: str) -> dict[str, Any] | None:
    idea = get_idea(settings, idea_id)
    if not idea:
        return None
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT e.id, e.summary, e.type, e.created_at, ie.link_type, ie.note
            FROM entries_index e
            JOIN idea_entries ie ON ie.entry_id = e.id
            WHERE ie.idea_id = ?
            ORDER BY e.created_at DESC
            LIMIT 50
            """,
            (idea_id,),
        ).fetchall()
    finally:
        conn.close()
    entries = [
        {
            "id": row["id"],
            "summary": row["summary"] or "",
            "type": row["type"],
            "created_at": row["created_at"],
            "link_type": row["link_type"],
            "note": row["note"] or "",
        }
        for row in rows
    ]
    return {**idea, "entries": entries}


def update_idea(
    settings,
    idea_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    current = get_idea(settings, idea_id)
    if not current or not current["is_current"]:
        return None

    allowed = {"title", "description", "status"}
    payload = {k: v for k, v in updates.items() if k in allowed}
    if not payload:
        return current

    now = utc_now_iso()
    new_status = str(payload.get("status", current["status"]))
    if new_status not in _IDEA_STATUSES:
        new_status = current["status"]

    new_title = str(payload.get("title", current["title"])).strip() or current["title"]
    new_desc = str(payload.get("description", current["description"])).strip()

    new_idea_id = f"idea-{uuid.uuid4()}"
    new_version = current["version_no"] + 1
    run_id = f"manual-{uuid.uuid4()}"
    payload_seed = {
        "logical_id": current["logical_id"],
        "title": new_title,
        "description": new_desc,
        "status": new_status,
        "version_no": new_version,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        _ensure_run(conn, run_id)
        conn.execute(
            "UPDATE ideas SET is_current = 0, updated_at = ? WHERE idea_id = ?",
            (now, idea_id),
        )
        conn.execute(
            """
            INSERT INTO ideas (
              idea_id, logical_id, title, description, status,
              converted_to_type, converted_to_id, source_entry_id, source_run_id,
              payload_hash, payload_hash_version, version_no, is_current,
              supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                new_idea_id, current["logical_id"], new_title, new_desc, new_status,
                current["converted_to_type"], current["converted_to_id"],
                current["source_entry_id"], run_id,
                payload_hash, PAYLOAD_HASH_VERSION, new_version,
                idea_id, current["created_at"], now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_idea(settings, new_idea_id)


def convert_idea(
    settings,
    idea_id: str,
    *,
    target_type: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target_type not in _CONVERT_TARGETS:
        raise ValueError(f"Invalid target_type: {target_type}")

    current = get_idea(settings, idea_id)
    if not current or not current["is_current"]:
        raise KeyError("Idea not found or not current.")

    extra = extra or {}
    now = utc_now_iso()
    run_id = f"manual-{uuid.uuid4()}"
    converted_id: str | None = None

    if target_type == "goal":
        from app.services.goals import create_goal
        goal = create_goal(
            settings,
            name=extra.get("name") or current["title"],
            start_date=extra.get("start_date") or now[:10],
        )
        converted_id = goal["goal_id"]
    elif target_type == "project":
        from app.services.projects import create_project
        project = create_project(
            settings,
            name=extra.get("name") or current["title"],
            kind=extra.get("kind", "personal"),
        )
        converted_id = project["project_id"]
    elif target_type == "task":
        from app.services.tasks import sync_tasks_from_actions
        actions_md = f"- [ ] {current['title']}"
        _ensure_run_global(settings, run_id)
        result = sync_tasks_from_actions(
            settings,
            entry_id=current.get("source_entry_id") or f"idea-{idea_id}",
            source_run_id=run_id,
            actions_md=actions_md,
        )
        converted_id = f"task-from-idea-{idea_id}"
        if result.get("task_ids"):
            converted_id = result["task_ids"][0]

    new_idea_id = f"idea-{uuid.uuid4()}"
    new_version = current["version_no"] + 1
    payload_seed = {
        "logical_id": current["logical_id"],
        "title": current["title"],
        "status": "converted",
        "converted_to_type": target_type,
        "converted_to_id": converted_id,
        "version_no": new_version,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        _ensure_run(conn, run_id)
        conn.execute(
            "UPDATE ideas SET is_current = 0, updated_at = ? WHERE idea_id = ?",
            (now, idea_id),
        )
        conn.execute(
            """
            INSERT INTO ideas (
              idea_id, logical_id, title, description, status,
              converted_to_type, converted_to_id, source_entry_id, source_run_id,
              payload_hash, payload_hash_version, version_no, is_current,
              supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'converted', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                new_idea_id, current["logical_id"], current["title"], current["description"],
                target_type, converted_id,
                current["source_entry_id"], run_id,
                payload_hash, PAYLOAD_HASH_VERSION, new_version,
                idea_id, current["created_at"], now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "idea": get_idea(settings, new_idea_id),
        "converted_to_type": target_type,
        "converted_to_id": converted_id,
    }


def _ensure_run_global(settings, run_id: str) -> None:
    conn = get_connection(settings)
    try:
        _ensure_run(conn, run_id)
        conn.commit()
    finally:
        conn.close()


def update_entry_link_note(
    settings,
    *,
    idea_id: str,
    entry_id: str,
    note: str,
) -> bool:
    conn = get_connection(settings)
    try:
        cur = conn.execute(
            """
            UPDATE idea_entries SET note = ?
            WHERE idea_id = ? AND entry_id = ?
            """,
            (note, idea_id, entry_id),
        )
        conn.commit()
    finally:
        conn.close()
    return cur.rowcount > 0


def ideas_context(settings) -> list[dict[str, Any]]:
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT idea_id, title, description, status
            FROM ideas
            WHERE is_current = 1 AND status NOT IN ('converted', 'dropped')
            ORDER BY updated_at DESC
            LIMIT 50
            """,
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "idea_id": row["idea_id"],
            "title": row["title"],
            "description": row["description"] or "",
            "status": row["status"],
        }
        for row in rows
    ]
