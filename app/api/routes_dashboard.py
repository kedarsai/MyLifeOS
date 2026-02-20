from __future__ import annotations

from datetime import date as _date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.db.engine import get_connection
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


_TYPE_CLASSES = {
    "activity": "type-activity",
    "sleep": "type-sleep",
    "food": "type-food",
    "thought": "type-thought",
    "idea": "type-idea",
    "todo": "type-todo",
    "goal": "type-goal",
    "note": "type-note",
    "chat": "type-chat",
}

_BULB_MAP = {
    "inbox": "bulb-orange",
    "processed": "bulb-green",
    "archived": "bulb-yellow",
}

_STATUS_LABEL = {
    "inbox": "Inbox",
    "processed": "Processed",
    "archived": "Archived",
}

_STATUS_CLS = {
    "inbox": "sb-inbox",
    "processed": "sb-processed",
    "archived": "sb-archived",
}


@router.get("/summary")
def summary(request: Request) -> Any:
    settings = request.app.state.settings
    conn = get_connection(settings)
    try:
        entry_counts = conn.execute(
            """
            SELECT status, COUNT(*) AS c
            FROM entries_index
            GROUP BY status
            """
        ).fetchall()
        by_status = {row["status"]: int(row["c"]) for row in entry_counts}

        open_conflicts = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM sync_conflicts WHERE conflict_status = 'open'"
            ).fetchone()["c"]
        )
        run_counts = conn.execute(
            """
            SELECT status, COUNT(*) AS c
            FROM prompt_runs
            GROUP BY status
            """
        ).fetchall()
        runs_by_status = {row["status"]: int(row["c"]) for row in run_counts}

        today_str = _date.today().isoformat()

        tasks_due_today = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM tasks
                WHERE is_current = 1
                  AND status IN ('open', 'in_progress')
                  AND due_date IS NOT NULL
                  AND due_date = ?
                """,
                (today_str,),
            ).fetchone()["c"]
        )

        tasks_due = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM tasks
                WHERE is_current = 1
                  AND status IN ('open', 'in_progress')
                  AND due_date IS NOT NULL
                  AND due_date <= ?
                """,
                (today_str,),
            ).fetchone()["c"]
        )

        open_thoughts = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM entries_index
                WHERE type = 'thought' AND status = 'inbox'
                """
            ).fetchone()["c"]
        )

        recent_entries = conn.execute(
            """
            SELECT id, created_at, type, status, summary, raw_text
            FROM entries_index
            ORDER BY created_at DESC, id DESC
            LIMIT 12
            """
        ).fetchall()

        recent_runs = conn.execute(
            """
            SELECT run_id, prompt_id, prompt_version, status, created_at, parse_ok
            FROM prompt_runs
            ORDER BY created_at DESC, run_id DESC
            LIMIT 8
            """
        ).fetchall()

    finally:
        conn.close()

    payload = {
        "entries": {
            "total": sum(by_status.values()),
            "inbox": by_status.get("inbox", 0),
            "processed": by_status.get("processed", 0),
            "archived": by_status.get("archived", 0),
        },
        "runs": {
            "total": sum(runs_by_status.values()),
            "pending": runs_by_status.get("pending", 0),
            "success": runs_by_status.get("success", 0),
            "failed": runs_by_status.get("failed", 0),
        },
        "conflicts": {"open": open_conflicts},
        "tasks_due_today": tasks_due_today,
        "tasks_due": tasks_due,
        "open_thoughts": open_thoughts,
        "recent_entries": [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "type": row["type"],
                "status": row["status"],
                "summary": row["summary"] or "",
                "raw_text": row["raw_text"] or "",
            }
            for row in recent_entries
        ],
        "recent_runs": [
            {
                "run_id": row["run_id"],
                "prompt_id": row["prompt_id"],
                "prompt_version": row["prompt_version"],
                "status": row["status"],
                "created_at": row["created_at"],
                "parse_ok": bool(row["parse_ok"]),
            }
            for row in recent_runs
        ],
    }

    if wants_html(request):
        return HTMLResponse(render(
            "fragments/dashboard_summary.html",
            entries=payload["entries"],
            runs=payload["runs"],
            tasks_due=payload["tasks_due"],
            tasks_due_today=payload["tasks_due_today"],
            open_thoughts=payload["open_thoughts"],
            recent_entries=payload["recent_entries"],
            type_classes=_TYPE_CLASSES,
            bulb_map=_BULB_MAP,
            status_cls_map=_STATUS_CLS,
            status_label_map=_STATUS_LABEL,
        ))
    return payload
