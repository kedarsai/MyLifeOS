from __future__ import annotations

import uuid
from typing import Any

from app.core.time import utc_now_iso
from app.db.engine import get_connection


def create_project(
    settings,
    *,
    name: str,
    kind: str = "personal",
    status: str = "active",
    notes: str = "",
) -> dict[str, Any]:
    now = utc_now_iso()
    project_id = f"project-{uuid.uuid4()}"
    conn = get_connection(settings)
    try:
        conn.execute(
            """
            INSERT INTO projects (project_id, name, kind, status, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, name.strip(), kind, status, notes.strip(), now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return get_project(settings, project_id)


def get_project(settings, project_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT p.project_id, p.name, p.kind, p.status, p.notes, p.created_at, p.updated_at,
                   COALESCE(tc.open_count, 0) AS open_tasks
            FROM projects p
            LEFT JOIN (
              SELECT tpl.project_id, COUNT(*) AS open_count
              FROM task_project_links tpl
              JOIN tasks t ON t.task_id = tpl.task_id
              WHERE t.is_current = 1 AND t.status IN ('open','in_progress')
              GROUP BY tpl.project_id
            ) tc ON tc.project_id = p.project_id
            WHERE p.project_id = ?
            """,
            (project_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "project_id": row["project_id"],
        "name": row["name"],
        "kind": row["kind"],
        "status": row["status"],
        "notes": row["notes"] or "",
        "open_tasks": int(row["open_tasks"] or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_projects(settings, *, status: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if status:
        where.append("p.status = ?")
        params.append(status)
    if kind:
        where.append("p.kind = ?")
        params.append(kind)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    conn = get_connection(settings)
    try:
        rows = conn.execute(
            f"""
            SELECT p.project_id, p.name, p.kind, p.status, p.notes, p.created_at, p.updated_at,
                   COALESCE(tc.open_count, 0) AS open_tasks
            FROM projects p
            LEFT JOIN (
              SELECT tpl.project_id, COUNT(*) AS open_count
              FROM task_project_links tpl
              JOIN tasks t ON t.task_id = tpl.task_id
              WHERE t.is_current = 1 AND t.status IN ('open','in_progress')
              GROUP BY tpl.project_id
            ) tc ON tc.project_id = p.project_id
            {where_sql}
            ORDER BY p.updated_at DESC, p.project_id DESC
            """,
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "project_id": row["project_id"],
            "name": row["name"],
            "kind": row["kind"],
            "status": row["status"],
            "notes": row["notes"] or "",
            "open_tasks": int(row["open_tasks"] or 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def update_project(settings, project_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    current = get_project(settings, project_id)
    if not current:
        return None
    allowed = {"name", "kind", "status", "notes"}
    payload = {k: v for k, v in updates.items() if k in allowed}
    if not payload:
        return current

    merged = dict(current)
    merged.update(payload)
    merged["updated_at"] = utc_now_iso()

    conn = get_connection(settings)
    try:
        conn.execute(
            """
            UPDATE projects
            SET name = ?, kind = ?, status = ?, notes = ?, updated_at = ?
            WHERE project_id = ?
            """,
            (
                str(merged["name"]).strip(),
                str(merged["kind"]),
                str(merged["status"]),
                str(merged.get("notes") or ""),
                merged["updated_at"],
                project_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_project(settings, project_id)
