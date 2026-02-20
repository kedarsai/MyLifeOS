from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from app.core.time import utc_now_iso
from app.db.engine import get_connection
from app.services.goals import goal_dashboard
from app.services.llm import run_openai_json_prompt
from app.services.prompts import WEEKLY_REVIEW_PROMPT_ID, WEEKLY_REVIEW_PROMPT_VERSION
from app.services.runs import record_prompt_run
from app.services.schema_validation import validate_prompt_output_schema
from app.vault.manager import VaultManager
from app.vault.markdown import dump_frontmatter


def _json_dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _week_bounds(week_start: str | None) -> tuple[str, str]:
    if week_start:
        start = date.fromisoformat(week_start)
    else:
        today = date.today()
        start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _review_markdown(
    goal: dict[str, Any],
    week_start: str,
    week_end: str,
    snapshot: dict[str, Any],
    review: dict[str, Any],
    *,
    source_run_id: str,
) -> str:
    fm = {
        "id": f"review-{goal['goal_id']}-{week_start}",
        "entity_type": "weekly_review",
        "goal_id": goal["goal_id"],
        "week_start": week_start,
        "week_end": week_end,
        "created": utc_now_iso(),
        "updated": utc_now_iso(),
        "source_run_id": source_run_id,
    }
    body: list[str] = [
        dump_frontmatter(fm),
        "\n## Title\n",
        f"Weekly Review: {goal['name']} ({week_start} to {week_end})\n",
        "\n## Snapshot\n",
        json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n",
        "\n## What's Going Well\n",
    ]
    for line in review["what_went_well"]:
        body.append(f"- {line}\n")
    body.append("\n## What's Not Going Well\n")
    for line in review["what_did_not_go_well"]:
        body.append(f"- {line}\n")
    body.append("\n## Patterns\n")
    for line in review["patterns"]:
        body.append(f"- {line}\n")
    body.append("\n## Next Actions\n")
    for action in review["next_best_actions"]:
        body.append(f"- [ ] {action['title']} ({action['priority']})\n")
    body.append("\n## Risk\n")
    body.append(f"- Level: {review['risk_level']}\n")
    body.append(f"- Confidence: {review['confidence']}\n")
    return "".join(body)


def _build_review_output(settings, *, goal_id: str, week_start: str, week_end: str) -> tuple[dict[str, Any], dict[str, Any]]:
    dashboard = goal_dashboard(settings, goal_id=goal_id)
    if not dashboard:
        raise KeyError("Goal not found.")
    goal = dashboard["goal"]
    metrics = dashboard["metrics"]

    deterministic_metrics: dict[str, Any] = {
        "steps_avg_7d": metrics.get("steps_avg_7d"),
        "steps_streak_days": metrics.get("step_streak_days"),
        "sleep_avg_min_7d": metrics.get("sleep_avg_min_7d"),
        "logging_completeness_pct": metrics.get("logging_completeness_7d_pct") or 0.0,
    }
    if metrics.get("weight_trend_kg_30d") is not None:
        deterministic_metrics["weight_trend_30d_kg_per_week"] = metrics["weight_trend_kg_30d"]

    from app.services.reminders import detect_missing_logs

    missing_rows = [
        item for item in detect_missing_logs(settings, days=7) if item["goal_id"] == goal_id and week_start <= item["date"] <= week_end
    ]
    missing_data = []
    for row in missing_rows:
        for metric in row["missing_types"]:
            missing_data.append({"metric": metric if metric in {"sleep", "food", "activity", "weight"} else "other", "date": row["date"]})

    logging_pct = float(deterministic_metrics["logging_completeness_pct"] or 0.0)
    sleep_avg = deterministic_metrics.get("sleep_avg_min_7d")
    step_streak = int(metrics.get("step_streak_days") or 0)
    risk_level = "low" if logging_pct >= 85 else ("medium" if logging_pct >= 50 else "high")
    confidence = 0.9 if logging_pct >= 85 else (0.75 if logging_pct >= 50 else 0.6)

    what_went_well = [
        f"Logging completeness reached {logging_pct:.1f}%.",
        f"Step streak is {step_streak} day(s).",
    ]
    if (sleep_avg or 0) >= 420:
        what_went_well.append("Average sleep duration is within target range.")

    what_not = []
    if (sleep_avg or 0) < 420:
        what_not.append("Sleep duration trend is below 7 hours.")
    if logging_pct < 60:
        what_not.append("Too many days are missing structured logs.")
    if not what_not:
        what_not.append("No major negative signal detected this week.")

    patterns = [
        f"Linked entries this week indicate {logging_pct:.1f}% consistency.",
        f"Current step streak remains at {step_streak} day(s).",
    ]
    if missing_data:
        patterns.append(f"Missing data points recorded: {len(missing_data)}.")

    next_actions = [
        {
            "title": "Complete one sleep and one activity log daily.",
            "priority": "high" if logging_pct < 60 else "medium",
            "rationale": "Consistent logging improves signal quality for coaching.",
        },
        {
            "title": "Schedule a 15-minute nightly planning block.",
            "priority": "medium",
            "rationale": "Pre-commitment increases execution consistency.",
        },
    ]

    review_output = {
        "goal_id": goal_id,
        "period": {
            "start_date": week_start,
            "end_date": week_end,
            "timezone": settings.timezone,
        },
        "deterministic_metrics": deterministic_metrics,
        "missing_data": missing_data[:30],
        "what_went_well": what_went_well[:10],
        "what_did_not_go_well": what_not[:10],
        "patterns": patterns[:12],
        "next_best_actions": next_actions[:8],
        "risk_level": risk_level,
        "confidence": confidence,
    }
    snapshot = {
        "goal_id": goal_id,
        "goal_name": goal["name"],
        "week_start": week_start,
        "week_end": week_end,
        "metrics": metrics,
        "missing_data_points": len(missing_data),
    }
    return snapshot, review_output


def generate_weekly_review(settings, *, goal_id: str, week_start: str | None = None) -> dict[str, Any]:
    start, end = _week_bounds(week_start)
    snapshot, deterministic_review = _build_review_output(settings, goal_id=goal_id, week_start=start, week_end=end)

    llm_error: str | None = None
    used_fallback = False
    review_output: dict[str, Any]
    try:
        review_output = run_openai_json_prompt(
            settings,
            prompt_id=WEEKLY_REVIEW_PROMPT_ID,
            prompt_version=WEEKLY_REVIEW_PROMPT_VERSION,
            model_override=settings.model_analysis,
            variables={
                "goal_context_json": _json_dump(
                    {
                        "snapshot": snapshot,
                        "deterministic_review": deterministic_review,
                    }
                ),
            },
        )
    except Exception as exc:
        used_fallback = True
        llm_error = str(exc)
        review_output = deterministic_review

    parse_ok, schema_error = validate_prompt_output_schema(
        settings,
        prompt_id=WEEKLY_REVIEW_PROMPT_ID,
        prompt_version=WEEKLY_REVIEW_PROMPT_VERSION,
        output=review_output,
    )
    if not parse_ok:
        used_fallback = True
        review_output = deterministic_review
        parse_ok, schema_error = validate_prompt_output_schema(
            settings,
            prompt_id=WEEKLY_REVIEW_PROMPT_ID,
            prompt_version=WEEKLY_REVIEW_PROMPT_VERSION,
            output=review_output,
        )

    run_status = "success" if parse_ok else "failed"
    run_error = f"schema: {schema_error}" if schema_error else None
    if llm_error:
        run_error = f"{run_error} | llm: {llm_error}" if run_error else f"llm: {llm_error}"
    run_id = record_prompt_run(
        settings,
        prompt_id=WEEKLY_REVIEW_PROMPT_ID,
        prompt_version=WEEKLY_REVIEW_PROMPT_VERSION,
        model=settings.model_analysis,
        status=run_status,
        input_refs=[goal_id, start, end],
        output=review_output,
        parse_ok=parse_ok,
        error_text=run_error,
    )
    if not parse_ok:
        raise ValueError(f"Review schema validation failed: {schema_error}")

    manager = VaultManager(settings)
    manager.ensure_layout()
    review_path = settings.vault_path / "reviews" / f"{goal_id}_{start}.md"
    dashboard = goal_dashboard(settings, goal_id=goal_id)
    if not dashboard:
        raise KeyError("Goal not found.")
    manager.atomic_write_text(
        review_path,
        _review_markdown(
            dashboard["goal"],
            start,
            end,
            snapshot,
            review_output,
            source_run_id=run_id,
        ),
    )

    conn = get_connection(settings)
    try:
        conn.execute(
            """
            INSERT INTO weekly_reviews (
              review_id, goal_id, path, week_start, week_end,
              snapshot_json, review_json, source_run_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(goal_id, week_start, week_end) DO UPDATE SET
              path=excluded.path,
              snapshot_json=excluded.snapshot_json,
              review_json=excluded.review_json,
              source_run_id=excluded.source_run_id,
              created_at=excluded.created_at
            """,
            (
                f"review-{goal_id}-{start}",
                goal_id,
                str(review_path),
                start,
                end,
                _json_dump(snapshot),
                _json_dump(review_output),
                run_id,
                utc_now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "review_id": f"review-{goal_id}-{start}",
        "goal_id": goal_id,
        "week_start": start,
        "week_end": end,
        "path": str(review_path),
        "snapshot": snapshot,
        "review": review_output,
        "source_run_id": run_id,
        "used_fallback": used_fallback,
    }


def list_weekly_reviews(settings, *, goal_id: str | None = None) -> list[dict[str, Any]]:
    where = ""
    params: tuple[Any, ...] = ()
    if goal_id:
        where = "WHERE goal_id = ?"
        params = (goal_id,)
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            f"""
            SELECT review_id, goal_id, path, week_start, week_end, snapshot_json, review_json, source_run_id, created_at
            FROM weekly_reviews
            {where}
            ORDER BY week_start DESC, review_id DESC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        out.append(
            {
                "review_id": row["review_id"],
                "goal_id": row["goal_id"],
                "path": row["path"],
                "week_start": row["week_start"],
                "week_end": row["week_end"],
                "snapshot": json.loads(row["snapshot_json"]),
                "review": json.loads(row["review_json"]),
                "source_run_id": row["source_run_id"],
                "created_at": row["created_at"],
            }
        )
    return out
