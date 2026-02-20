from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.time import utc_now_iso
from app.db.engine import get_connection


def _json_dump(value: Any, default: Any) -> str:
    if value is None:
        value = default
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _json_load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def create_goal(
    settings,
    *,
    name: str,
    start_date: str,
    end_date: str | None = None,
    rules_md: str = "",
    metrics: list[str] | None = None,
    status: str = "active",
    review_cadence_days: int = 7,
) -> dict[str, Any]:
    now = utc_now_iso()
    goal_id = f"goal-{uuid.uuid4()}"
    path = f"{settings.vault_path.as_posix()}/goals/{goal_id}.md"
    conn = get_connection(settings)
    try:
        conn.execute(
            """
            INSERT INTO goals (
              goal_id, path, name, start_date, end_date, rules_md, metrics_json,
              status, review_cadence_days, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                goal_id,
                path,
                name.strip(),
                start_date,
                end_date,
                rules_md,
                _json_dump(metrics, []),
                status,
                int(review_cadence_days),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_goal(settings, goal_id)


def list_goals(settings, *, status: str | None = None) -> list[dict[str, Any]]:
    where = ""
    params: tuple[Any, ...] = ()
    if status:
        where = "WHERE status = ?"
        params = (status,)
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            f"""
            SELECT goal_id, path, name, start_date, end_date, rules_md, metrics_json, status,
                   review_cadence_days, created_at, updated_at
            FROM goals
            {where}
            ORDER BY updated_at DESC, goal_id DESC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "goal_id": row["goal_id"],
            "path": row["path"],
            "name": row["name"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "rules_md": row["rules_md"] or "",
            "metrics": _json_load(row["metrics_json"], []),
            "status": row["status"],
            "review_cadence_days": int(row["review_cadence_days"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_goal(settings, goal_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT goal_id, path, name, start_date, end_date, rules_md, metrics_json, status,
                   review_cadence_days, created_at, updated_at
            FROM goals
            WHERE goal_id = ?
            """,
            (goal_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "goal_id": row["goal_id"],
        "path": row["path"],
        "name": row["name"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "rules_md": row["rules_md"] or "",
        "metrics": _json_load(row["metrics_json"], []),
        "status": row["status"],
        "review_cadence_days": int(row["review_cadence_days"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def update_goal(settings, goal_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    current = get_goal(settings, goal_id)
    if not current:
        return None

    allowed = {
        "name",
        "start_date",
        "end_date",
        "rules_md",
        "metrics",
        "status",
        "review_cadence_days",
    }
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
            UPDATE goals
            SET name = ?, start_date = ?, end_date = ?, rules_md = ?, metrics_json = ?,
                status = ?, review_cadence_days = ?, updated_at = ?
            WHERE goal_id = ?
            """,
            (
                merged["name"],
                merged["start_date"],
                merged["end_date"],
                merged["rules_md"],
                _json_dump(merged["metrics"], []),
                merged["status"],
                int(merged["review_cadence_days"]),
                merged["updated_at"],
                goal_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_goal(settings, goal_id)


def link_entry_to_goal(settings, *, goal_id: str, entry_id: str, link_type: str = "related") -> bool:
    conn = get_connection(settings)
    try:
        exists_goal = conn.execute("SELECT 1 FROM goals WHERE goal_id = ?", (goal_id,)).fetchone()
        exists_entry = conn.execute("SELECT 1 FROM entries_index WHERE id = ?", (entry_id,)).fetchone()
        if not exists_goal or not exists_entry:
            return False
        conn.execute(
            """
            INSERT INTO goal_links (goal_id, entry_id, link_type)
            VALUES (?, ?, ?)
            ON CONFLICT(goal_id, entry_id, link_type) DO NOTHING
            """,
            (goal_id, entry_id, link_type),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def goal_dashboard(settings, *, goal_id: str) -> dict[str, Any] | None:
    goal = get_goal(settings, goal_id)
    if not goal:
        return None

    conn = get_connection(settings)
    try:
        linked_entries = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM goal_links WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()["c"]
        )
        steps_avg_7d = conn.execute(
            """
            SELECT AVG(steps) AS v
            FROM obs_activity oa
            JOIN goal_links gl ON gl.entry_id = oa.entry_id
            WHERE gl.goal_id = ? AND oa.is_current = 1 AND date(oa.created_at) >= date('now','-6 day')
            """,
            (goal_id,),
        ).fetchone()["v"]
        sleep_avg_7d = conn.execute(
            """
            SELECT AVG(duration_min) AS v
            FROM obs_sleep os
            JOIN goal_links gl ON gl.entry_id = os.entry_id
            WHERE gl.goal_id = ? AND os.is_current = 1 AND date(os.created_at) >= date('now','-6 day')
            """,
            (goal_id,),
        ).fetchone()["v"]
        weight_rows = conn.execute(
            """
            SELECT weight_kg
            FROM obs_weight ow
            JOIN goal_links gl ON gl.entry_id = ow.entry_id
            WHERE gl.goal_id = ? AND ow.is_current = 1 AND date(ow.created_at) >= date('now','-30 day')
            ORDER BY ow.created_at ASC
            """,
            (goal_id,),
        ).fetchall()
        logging_days = conn.execute(
            """
            SELECT COUNT(DISTINCT date(e.created_at)) AS c
            FROM entries_index e
            JOIN goal_links gl ON gl.entry_id = e.id
            WHERE gl.goal_id = ? AND date(e.created_at) >= date('now','-6 day')
            """,
            (goal_id,),
        ).fetchone()["c"]
        streak_rows = conn.execute(
            """
            SELECT DISTINCT date(oa.created_at) AS d
            FROM obs_activity oa
            JOIN goal_links gl ON gl.entry_id = oa.entry_id
            WHERE gl.goal_id = ? AND oa.is_current = 1
            ORDER BY d DESC
            """,
            (goal_id,),
        ).fetchall()
        latest_review_row = conn.execute(
            """
            SELECT review_id, week_start, week_end, review_json, created_at
            FROM weekly_reviews
            WHERE goal_id = ?
            ORDER BY week_start DESC, created_at DESC
            LIMIT 1
            """,
            (goal_id,),
        ).fetchone()
    finally:
        conn.close()

    # streak by consecutive logged days
    streak = 0
    if streak_rows:
        from datetime import date, timedelta

        days = [date.fromisoformat(row["d"]) for row in streak_rows if row["d"]]
        if days:
            current = days[0]
            streak = 1
            for d in days[1:]:
                if d == current - timedelta(days=1):
                    streak += 1
                    current = d
                else:
                    break

    weight_trend = None
    if len(weight_rows) >= 2:
        weight_trend = float(weight_rows[-1]["weight_kg"]) - float(weight_rows[0]["weight_kg"])

    latest_review = None
    if latest_review_row:
        latest_review = {
            "review_id": latest_review_row["review_id"],
            "week_start": latest_review_row["week_start"],
            "week_end": latest_review_row["week_end"],
            "review": _json_load(latest_review_row["review_json"], {}),
            "created_at": latest_review_row["created_at"],
        }

    return {
        "goal": goal,
        "metrics": {
            "steps_avg_7d": round(float(steps_avg_7d), 2) if steps_avg_7d is not None else None,
            "step_streak_days": streak,
            "sleep_avg_min_7d": round(float(sleep_avg_7d), 2) if sleep_avg_7d is not None else None,
            "weight_trend_kg_30d": round(float(weight_trend), 3) if weight_trend is not None else None,
            "logging_completeness_7d_pct": round((int(logging_days or 0) / 7.0) * 100.0, 1),
            "linked_entries": linked_entries,
        },
        "latest_review": latest_review,
    }
