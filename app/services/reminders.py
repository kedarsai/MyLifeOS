from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.db.engine import get_connection


def detect_missing_logs(settings, *, days: int = 7) -> list[dict[str, Any]]:
    conn = get_connection(settings)
    try:
        goals = conn.execute(
            "SELECT goal_id, name FROM goals WHERE status = 'active' ORDER BY goal_id"
        ).fetchall()
        rows = conn.execute(
            """
            SELECT gl.goal_id AS goal_id, date(e.created_at) AS d, e.type AS type
            FROM goal_links gl
            JOIN entries_index e ON e.id = gl.entry_id
            WHERE date(e.created_at) >= date('now', ?)
            """,
            (f"-{max(1, int(days)) - 1} day",),
        ).fetchall()
    finally:
        conn.close()

    observed: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        key = (row["goal_id"], row["d"])
        observed.setdefault(key, set()).add(str(row["type"]))

    required = {"activity", "sleep", "food"}
    today = date.today()
    out: list[dict[str, Any]] = []
    for goal in goals:
        gid = goal["goal_id"]
        for i in range(max(1, int(days))):
            day = (today - timedelta(days=i)).isoformat()
            missing = sorted(required - observed.get((gid, day), set()))
            if missing:
                out.append(
                    {
                        "goal_id": gid,
                        "goal_name": goal["name"],
                        "date": day,
                        "missing_types": missing,
                    }
                )
    return out


def reminders_summary(settings) -> dict[str, Any]:
    conn = get_connection(settings)
    try:
        open_conflicts = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM sync_conflicts WHERE conflict_status = 'open'"
            ).fetchone()["c"]
        )
        failed_runs = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM prompt_runs WHERE status = 'failed'"
            ).fetchone()["c"]
        )
        stale_improvements = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM improvements
                WHERE is_current = 1
                  AND status IN ('open','in_progress')
                  AND (last_nudged_at IS NULL OR date(last_nudged_at) <= date('now','-7 day'))
                """
            ).fetchone()["c"]
        )
        review_rows = conn.execute(
            """
            SELECT g.goal_id, g.name, g.review_cadence_days, MAX(wr.week_end) AS last_week_end
            FROM goals g
            LEFT JOIN weekly_reviews wr ON wr.goal_id = g.goal_id
            WHERE g.status = 'active'
            GROUP BY g.goal_id, g.name, g.review_cadence_days
            """
        ).fetchall()
    finally:
        conn.close()
    missing = detect_missing_logs(settings, days=7)
    due_reviews = []
    today = date.today()
    for row in review_rows:
        cadence = int(row["review_cadence_days"] or 7)
        last_end = row["last_week_end"]
        if not last_end:
            due_reviews.append({"goal_id": row["goal_id"], "goal_name": row["name"], "days_since_review": None})
            continue
        try:
            last_end_day = date.fromisoformat(str(last_end))
        except ValueError:
            due_reviews.append({"goal_id": row["goal_id"], "goal_name": row["name"], "days_since_review": None})
            continue
        days_since = (today - last_end_day).days
        if days_since >= cadence:
            due_reviews.append({"goal_id": row["goal_id"], "goal_name": row["name"], "days_since_review": days_since})
    return {
        "counts": {
            "missing_logs": len(missing),
            "open_conflicts": open_conflicts,
            "failed_runs": failed_runs,
            "stale_improvements": stale_improvements,
            "due_reviews": len(due_reviews),
        },
        "missing_logs": missing,
        "due_reviews": due_reviews,
    }


def backup_status(settings) -> dict[str, Any]:
    base = Path("backups")
    hourly = base / "hourly"
    daily = base / "daily"
    hourly_latest = sorted(hourly.glob("*.zip"))[-1].name if hourly.exists() and list(hourly.glob("*.zip")) else None
    daily_latest = sorted(daily.glob("*.zip"))[-1].name if daily.exists() and list(daily.glob("*.zip")) else None
    return {
        "hourly_latest": hourly_latest,
        "daily_latest": daily_latest,
        "hourly_path": str(hourly),
        "daily_path": str(daily),
        "db_path": str(settings.db_path),
        "vault_path": str(settings.vault_path),
    }
