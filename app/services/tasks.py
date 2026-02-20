from __future__ import annotations

import re
import uuid
from typing import Any

from app.core.hashing import PAYLOAD_HASH_VERSION, canonical_payload_hash
from app.core.time import utc_now_iso
from app.db.engine import get_connection


_CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<done>[ xX])\]\s*(?P<title>.+?)\s*$")
_DUE_RE = re.compile(r"\bdue:(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)


def _normalize_title(title: str) -> str:
    clean = " ".join((title or "").split())
    return clean.strip()


def _logical_id(entry_id: str, title: str) -> str:
    seed = f"{entry_id}:{title.lower()}"
    return f"task-{uuid.uuid5(uuid.NAMESPACE_URL, seed)}"


def _extract_actions(actions_md: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in (actions_md or "").splitlines():
        m = _CHECKBOX_RE.match(raw)
        if not m:
            continue
        done = m.group("done").strip().lower() == "x"
        title = _normalize_title(m.group("title"))
        due = None
        dm = _DUE_RE.search(title)
        if dm:
            due = dm.group(1)
            title = _normalize_title(_DUE_RE.sub("", title))
        if not title:
            continue
        out.append({"title": title, "status": "done" if done else "open", "due_date": due})
    return out


def _goal_or_none(conn, goal_id: str | None) -> str | None:
    if not goal_id:
        return None
    row = conn.execute("SELECT 1 FROM goals WHERE goal_id = ?", (goal_id,)).fetchone()
    return goal_id if row else None


def _entry_or_none(conn, entry_id: str | None) -> str | None:
    if not entry_id:
        return None
    row = conn.execute("SELECT 1 FROM entries_index WHERE id = ?", (entry_id,)).fetchone()
    return entry_id if row else None


def _project_or_none(conn, project_id: str | None) -> str | None:
    if not project_id:
        return None
    row = conn.execute("SELECT 1 FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    return project_id if row else None


def sync_tasks_from_actions(
    settings,
    *,
    entry_id: str,
    source_run_id: str,
    actions_md: str,
    goal_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    items = _extract_actions(actions_md)
    if not items:
        return {"created": 0, "updated": 0, "task_ids": []}

    now = utc_now_iso()
    created = 0
    updated = 0
    task_ids: list[str] = []

    conn = get_connection(settings)
    try:
        safe_goal_id = _goal_or_none(conn, goal_id)
        safe_entry_id = _entry_or_none(conn, entry_id)
        safe_project_id = _project_or_none(conn, project_id)
        for item in items:
            logical_id = _logical_id(entry_id, item["title"])
            payload_seed = {
                "logical_id": logical_id,
                "entry_id": entry_id,
                "title": item["title"],
                "due_date": item["due_date"],
                "status": item["status"],
                "goal_id": safe_goal_id,
            }
            payload_hash = canonical_payload_hash(payload_seed)
            current = conn.execute(
                """
                SELECT task_id, version_no, payload_hash
                FROM tasks
                WHERE logical_id = ? AND is_current = 1
                ORDER BY version_no DESC
                LIMIT 1
                """,
                (logical_id,),
            ).fetchone()

            if current and current["payload_hash"] == payload_hash:
                task_ids.append(str(current["task_id"]))
                if safe_project_id:
                    conn.execute(
                        """
                        INSERT INTO task_project_links (task_id, project_id, linked_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(task_id) DO UPDATE SET
                          project_id = excluded.project_id,
                          linked_at = excluded.linked_at
                        """,
                        (str(current["task_id"]), safe_project_id, now),
                    )
                continue

            if current:
                conn.execute(
                    "UPDATE tasks SET is_current = 0 WHERE logical_id = ? AND task_id <> ?",
                    (logical_id, str(current["task_id"])),
                )
                version_no = int(current["version_no"]) + 1
                supersedes = str(current["task_id"])
                updated += 1
            else:
                version_no = 1
                supersedes = None
                created += 1

            task_id = f"task-{uuid.uuid4()}"
            conn.execute(
                """
                INSERT INTO tasks (
                  task_id, logical_id, path, source_entry_id, source_run_id, goal_id, title,
                  due_date, priority, status, rationale, payload_hash, payload_hash_version,
                  version_no, is_current, supersedes_id, created_at, updated_at
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 'medium', ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    task_id,
                    logical_id,
                    safe_entry_id,
                    source_run_id,
                    safe_goal_id,
                    item["title"],
                    item["due_date"],
                    item["status"],
                    f"Synced from entry {entry_id}",
                    payload_hash,
                    PAYLOAD_HASH_VERSION,
                    version_no,
                    supersedes,
                    now,
                    now,
                ),
            )
            if safe_project_id:
                conn.execute(
                    """
                    INSERT INTO task_project_links (task_id, project_id, linked_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                      project_id = excluded.project_id,
                      linked_at = excluded.linked_at
                    """,
                    (task_id, safe_project_id, now),
                )
            task_ids.append(task_id)
        conn.commit()
    finally:
        conn.close()
    return {"created": created, "updated": updated, "task_ids": task_ids}


def list_tasks(
    settings,
    *,
    status: str | None = None,
    goal_id: str | None = None,
    project_id: str | None = None,
    q: str | None = None,
    limit: int = 200,
    include_done: bool = False,
) -> dict[str, Any]:
    where = ["t.is_current = 1"]
    params: list[Any] = []

    if status:
        where.append("t.status = ?")
        params.append(status)
    elif not include_done:
        where.append("t.status IN ('open','in_progress')")
    if goal_id:
        where.append("t.goal_id = ?")
        params.append(goal_id)
    if project_id:
        where.append("tpl.project_id = ?")
        params.append(project_id)
    if q:
        where.append("(lower(t.title) LIKE ? OR lower(COALESCE(t.rationale,'')) LIKE ?)")
        like = f"%{q.lower()}%"
        params.extend([like, like])

    where_sql = " AND ".join(where)
    conn = get_connection(settings)
    try:
        total = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM tasks t
                LEFT JOIN task_project_links tpl ON tpl.task_id = t.task_id
                WHERE {where_sql}
                """,
                tuple(params),
            ).fetchone()["c"]
        )
        rows = conn.execute(
            f"""
            SELECT
              t.task_id, t.logical_id, t.title, t.due_date, t.priority, t.status, t.goal_id, t.updated_at,
              t.rationale,
              g.name AS goal_name,
              tpl.project_id,
              p.name AS project_name,
              p.kind AS project_kind
            FROM tasks t
            LEFT JOIN goals g ON g.goal_id = t.goal_id
            LEFT JOIN task_project_links tpl ON tpl.task_id = t.task_id
            LEFT JOIN projects p ON p.project_id = tpl.project_id
            WHERE {where_sql}
            ORDER BY
              CASE t.status WHEN 'open' THEN 1 WHEN 'in_progress' THEN 2 ELSE 3 END,
              CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
              COALESCE(t.due_date, '9999-12-31'),
              t.updated_at DESC
            LIMIT ?
            """,
            (*params, int(limit)),
        ).fetchall()
    finally:
        conn.close()

    return {
        "items": [
            {
                "task_id": row["task_id"],
                "logical_id": row["logical_id"],
                "title": row["title"],
                "due_date": row["due_date"],
                "priority": row["priority"],
                "status": row["status"],
                "goal_id": row["goal_id"],
                "goal_name": row["goal_name"],
                "project_id": row["project_id"],
                "project_name": row["project_name"],
                "project_kind": row["project_kind"],
                "rationale": row["rationale"] or "",
                "updated_at": row["updated_at"],
            }
            for row in rows
        ],
        "total": total,
    }


def list_today_tasks(settings) -> dict[str, list[dict[str, Any]]]:
    conn = get_connection(settings)
    try:
        today_str = conn.execute("SELECT date('now') AS d").fetchone()["d"]
    finally:
        conn.close()

    all_open = list_tasks(settings, include_done=False, limit=1000)["items"]
    due_today = []
    overdue = []
    next_actions = []
    for item in all_open:
        due = item["due_date"]
        if not due:
            next_actions.append(item)
        elif str(due) < today_str:
            overdue.append(item)
        elif str(due) == today_str:
            due_today.append(item)
        else:
            next_actions.append(item)
    return {"today": today_str, "due_today": due_today, "overdue": overdue, "next_actions": next_actions}


def quick_complete_task(settings, task_id: str) -> bool:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE task_id = ? AND is_current = 1",
            (task_id,),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE tasks SET status = 'done', updated_at = ? WHERE task_id = ?",
            (utc_now_iso(), task_id),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def assign_task_project(settings, *, task_id: str, project_id: str | None) -> bool:
    conn = get_connection(settings)
    try:
        exists_task = conn.execute(
            "SELECT 1 FROM tasks WHERE task_id = ? AND is_current = 1",
            (task_id,),
        ).fetchone()
        if not exists_task:
            return False
        safe_project = _project_or_none(conn, project_id)
        if project_id and not safe_project:
            return False
        if safe_project:
            conn.execute(
                """
                INSERT INTO task_project_links (task_id, project_id, linked_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                  project_id = excluded.project_id,
                  linked_at = excluded.linked_at
                """,
                (task_id, safe_project, utc_now_iso()),
            )
        else:
            conn.execute("DELETE FROM task_project_links WHERE task_id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()
    return True


def delete_task(settings, task_id: str) -> bool:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT logical_id FROM tasks WHERE task_id = ? AND is_current = 1",
            (task_id,),
        ).fetchone()
        if not row:
            return False
        logical_id = str(row["logical_id"])
        task_rows = conn.execute("SELECT task_id FROM tasks WHERE logical_id = ?", (logical_id,)).fetchall()
        task_ids = [str(item["task_id"]) for item in task_rows]
        if task_ids:
            placeholders = ",".join("?" for _ in task_ids)
            conn.execute(f"DELETE FROM task_project_links WHERE task_id IN ({placeholders})", tuple(task_ids))
            conn.execute(f"DELETE FROM tasks WHERE task_id IN ({placeholders})", tuple(task_ids))
        conn.commit()
    finally:
        conn.close()
    return True
