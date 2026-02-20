from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.time import utc_now_iso
from app.db.engine import get_connection
from app.services.distill import distill_raw_text
from app.services.improvements import create_improvement
from app.services.indexer import VaultIndexer
from app.services.llm import run_openai_json_prompt
from app.services.observations import (
    upsert_activity_observation,
    upsert_food_observation,
    upsert_sleep_observation,
    upsert_weight_observation,
)
from app.services.projects import list_projects
from app.services.goals import list_goals
from app.services.prompts import (
    DEFAULT_PROMPT_ID,
    DEFAULT_PROMPT_VERSION,
    ensure_default_prompt_assets,
    load_prompt_templates,
)
from app.services.runs import record_prompt_run
from app.services.schema_validation import validate_prompt_output_schema
from app.services.tasks import sync_tasks_from_actions
from app.vault.manager import VaultManager
from app.vault.markdown import parse_markdown_note, render_entry_note


_ENTRY_TYPES = {
    "activity",
    "sleep",
    "food",
    "thought",
    "idea",
    "todo",
    "goal",
    "note",
    "chat",
}
_CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<done>[ xX])\]\s*(?P<title>.+?)\s*$")
_DUE_RE = re.compile(r"\bdue:(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
_ACTION_VERB_START_RE = re.compile(
    r"^\s*(?:please\s+)?(?:complete|finish|ship|submit|send|update|review|fix|prepare|draft|write|plan|create|build|map|deploy|call|email)\b",
    re.IGNORECASE,
)
_ACTION_INTENT_RE = re.compile(r"^\s*(?:i\s+)?(?:need|want|plan|have)\s+to\b", re.IGNORECASE)
_URGENCY_HINT_RE = re.compile(r"\b(today|tomorrow|tonight|asap|eod|end of day)\b", re.IGNORECASE)


@dataclass
class EntryQueryResult:
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


@dataclass
class ProcessInboxResult:
    selected_count: int
    processed_ids: list[str]
    failed_ids: list[str]
    missing_paths: list[str]
    run_ids: list[str]
    observations_indexed: int
    tasks_synced: int
    improvements_created: int


def _json_dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _json_array(text: Any) -> list[str]:
    if isinstance(text, list):
        return [str(v) for v in text]
    if not isinstance(text, str) or not text.strip():
        return []
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(v) for v in value]


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in out:
            out.append(item)
    return out


def _normalize_entry_type(value: Any, fallback: str = "note") -> str:
    item = str(value or "").strip().lower()
    if item in _ENTRY_TYPES:
        return item
    return fallback if fallback in _ENTRY_TYPES else "note"


def _extract_actions_from_md(actions_md: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for raw in (actions_md or "").splitlines():
        match = _CHECKBOX_RE.match(raw)
        if not match:
            continue
        title = str(match.group("title")).strip()
        if not title:
            continue
        due_date = None
        due_match = _DUE_RE.search(title)
        if due_match:
            due_date = due_match.group(1)
            title = _DUE_RE.sub("", title).strip()
        if not title:
            continue
        status = "done" if match.group("done").strip().lower() == "x" else "open"
        action: dict[str, Any] = {
            "title": title,
            "priority": "medium",
            "status": status,
            "due_date": due_date,
            "goal_id": None,
            "rationale": None,
        }
        actions.append(action)
    return actions


def _todo_default_action(raw_text: str, summary: str) -> dict[str, Any]:
    text = " ".join((raw_text or "").strip().split())
    title_source = text or (summary or "").strip() or "Review task"
    due_date = None
    due_match = _DUE_RE.search(title_source)
    if due_match:
        due_date = due_match.group(1)
        title_source = _DUE_RE.sub("", title_source).strip()
    lowered = title_source.lower()
    for prefix in ("todo:", "action:"):
        idx = lowered.find(prefix)
        if idx >= 0:
            title_source = title_source[idx + len(prefix) :].strip()
            break
    if len(title_source) > 200:
        title_source = title_source[:197] + "..."
    action: dict[str, Any] = {
        "title": title_source or "Review task",
        "priority": "medium",
        "status": "open",
        "due_date": due_date,
        "goal_id": None,
        "rationale": None,
    }
    return action


def _is_actionable_raw_text(raw_text: str) -> bool:
    normalized = " ".join((raw_text or "").strip().split())
    if not normalized:
        return False
    lowered = normalized.lower()
    if "todo:" in lowered or "action:" in lowered:
        return True
    if _ACTION_VERB_START_RE.match(normalized):
        return True
    if _URGENCY_HINT_RE.search(normalized) and _ACTION_INTENT_RE.match(normalized):
        return True
    return False


def _local_today_iso(settings) -> str:
    tz_name = str(getattr(settings, "timezone", "") or "UTC").strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    return datetime.now(tz).date().isoformat()


def _infer_relative_due_date(text: str, *, today_iso: str) -> str | None:
    normalized = " ".join((text or "").strip().lower().split())
    if not normalized:
        return None
    if re.search(r"\btomorrow\b", normalized):
        return (datetime.fromisoformat(today_iso).date() + timedelta(days=1)).isoformat()
    if re.search(r"\b(today|tonight)\b", normalized):
        return today_iso
    if "end of day" in normalized or re.search(r"\beod\b", normalized):
        return today_iso
    return None


def _apply_inferred_due_dates(
    actions: list[dict[str, Any]],
    *,
    raw_text: str,
    settings,
) -> list[dict[str, Any]]:
    if not actions:
        return []
    today_iso = _local_today_iso(settings)
    allow_raw_fallback = len(actions) == 1
    out: list[dict[str, Any]] = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        due_text = str(normalized.get("due_date") or "").strip()
        if not due_text:
            title_text = str(normalized.get("title") or "")
            inferred = _infer_relative_due_date(title_text, today_iso=today_iso)
            if not inferred and allow_raw_fallback:
                inferred = _infer_relative_due_date(raw_text, today_iso=today_iso)
            if inferred:
                normalized["due_date"] = inferred
        out.append(normalized)
    return out


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _apply_ingest_tool_calls(
    actions: list[dict[str, Any]],
    *,
    tool_calls: Any,
    settings,
) -> list[dict[str, Any]]:
    if not actions:
        return []
    calls = tool_calls if isinstance(tool_calls, list) else []
    if not calls:
        return actions
    today = datetime.fromisoformat(_local_today_iso(settings)).date()
    out = [dict(item) if isinstance(item, dict) else {} for item in actions]
    for call in calls:
        if not isinstance(call, dict):
            continue
        name = str(call.get("name") or "").strip()
        args = call.get("arguments")
        if not isinstance(args, dict):
            continue
        idx = _as_int(args.get("action_index"))
        if idx is None or idx < 0 or idx >= len(out):
            continue
        if name == "resolve_relative_due_date":
            offset_days = _as_int(args.get("offset_days"))
            if offset_days is None:
                continue
            out[idx]["due_date"] = (today + timedelta(days=offset_days)).isoformat()
        elif name == "set_due_date":
            date_text = str(args.get("date") or "").strip()
            if not date_text:
                continue
            try:
                parsed = datetime.fromisoformat(date_text).date().isoformat()
            except ValueError:
                continue
            out[idx]["due_date"] = parsed
    return out


def _render_details_md(details_bullets: Any) -> str:
    bullets = [str(v).strip() for v in (details_bullets or []) if str(v).strip()]
    if not bullets:
        return "-"
    return "\n".join(f"- {bullet}" for bullet in bullets)


def _render_actions_md(actions: Any) -> str:
    if not isinstance(actions, list) or not actions:
        return "-"
    lines: list[str] = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        status = str(item.get("status") or "open").strip().lower()
        marker = "x" if status == "done" else " "
        due_date = str(item.get("due_date") or "").strip()
        suffix = f" due:{due_date}" if due_date else ""
        lines.append(f"- [{marker}] {title}{suffix}")
    return "\n".join(lines) if lines else "-"


def _goal_context(settings) -> tuple[list[dict[str, Any]], set[str]]:
    goals = list_goals(settings, status="active")
    goal_ids = {str(item["goal_id"]) for item in goals}
    compact = [
        {
            "goal_id": item["goal_id"],
            "name": item["name"],
            "status": item["status"],
            "metrics": item["metrics"],
        }
        for item in goals
    ]
    return compact, goal_ids


def _project_context(settings) -> tuple[list[dict[str, Any]], set[str]]:
    projects = list_projects(settings, status="active")
    project_ids = {str(item["project_id"]) for item in projects}
    compact = [
        {
            "project_id": item["project_id"],
            "name": item["name"],
            "kind": item["kind"],
            "status": item["status"],
        }
        for item in projects
    ]
    return compact, project_ids


def _fallback_ingest_output(
    *,
    raw_text: str,
    created_at: str,
    fallback_entry_type: str,
    existing_tags: list[str],
    existing_goals: list[str],
    goal_ids: set[str],
) -> dict[str, Any]:
    distilled = distill_raw_text(raw_text, existing_tags=existing_tags)
    details = [line.strip("- ").strip() for line in distilled["details_md"].splitlines() if line.strip()]
    actions = _extract_actions_from_md(distilled["actions_md"])
    safe_goal_ids = [goal for goal in existing_goals if goal in goal_ids]
    raw_lower = raw_text.lower()
    needs_followup = (
        "improve" in raw_lower
        or "could be better" in raw_lower
        or "need to fix" in raw_lower
        or "blocked" in raw_lower
    )
    followups: list[str] = []
    if needs_followup:
        followups.append("What is one concrete next step to improve this area tomorrow?")
    normalized_entry_type = _normalize_entry_type(fallback_entry_type)
    if (normalized_entry_type == "todo" or _is_actionable_raw_text(raw_text)) and not actions:
        actions = [_todo_default_action(raw_text, distilled["summary"])]
    return {
        "entry_type": normalized_entry_type,
        "summary": distilled["summary"],
        "details_bullets": details[:20] if details else ["Captured note."],
        "tags": distilled["tags"][:30],
        "goal_links": [{"goal_id": gid, "link_type": "related"} for gid in safe_goal_ids[:20]],
        "observations": {
            "activity": [],
            "sleep": [],
            "food": [],
            "weight": [],
        },
        "actions": actions[:20],
        "tool_calls": [],
        "needs_followup": needs_followup,
        "followup_questions": followups[:8],
        "confidence": 0.55,
        "_meta_created_at": created_at,
    }


def _prepare_ingest_output(
    settings,
    *,
    raw_text: str,
    created_at: str,
    fallback_entry_type: str,
    existing_tags: list[str],
    existing_goals: list[str],
    goals_context: list[dict[str, Any]],
    goal_ids: set[str],
    projects_context: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool, str | None]:
    fallback_output = _fallback_ingest_output(
        raw_text=raw_text,
        created_at=created_at,
        fallback_entry_type=fallback_entry_type,
        existing_tags=existing_tags,
        existing_goals=existing_goals,
        goal_ids=goal_ids,
    )

    llm_error: str | None = None
    used_fallback = False
    output: dict[str, Any]
    try:
        output = run_openai_json_prompt(
            settings,
            prompt_id=DEFAULT_PROMPT_ID,
            prompt_version=DEFAULT_PROMPT_VERSION,
            model_override=settings.model_ingest,
            variables={
                "raw_text": raw_text,
                "existing_tags_json": _json_dump(existing_tags),
                "goals_context_json": _json_dump(goals_context),
                "projects_context_json": _json_dump(projects_context),
                "created_at": created_at,
            },
        )
    except Exception as exc:
        used_fallback = True
        llm_error = str(exc)
        output = fallback_output

    parse_ok, schema_error = validate_prompt_output_schema(
        settings,
        prompt_id=DEFAULT_PROMPT_ID,
        prompt_version=DEFAULT_PROMPT_VERSION,
        output=output,
    )
    if not parse_ok:
        used_fallback = True
        fallback_clean = dict(fallback_output)
        fallback_clean.pop("_meta_created_at", None)
        output = fallback_clean
        parse_ok, fallback_schema_error = validate_prompt_output_schema(
            settings,
            prompt_id=DEFAULT_PROMPT_ID,
            prompt_version=DEFAULT_PROMPT_VERSION,
            output=output,
        )
        if not parse_ok:
            reason = fallback_schema_error or schema_error or "unknown schema validation error"
            return output, used_fallback, f"schema: {reason}"

    output.pop("_meta_created_at", None)
    return output, used_fallback, llm_error


def _safe_goal_ids(output: dict[str, Any], existing_goals: list[str], goal_ids: set[str]) -> list[str]:
    resolved: list[str] = []
    for goal in existing_goals:
        item = str(goal).strip()
        if item and item not in resolved:
            resolved.append(item)
    for link in output.get("goal_links") or []:
        if not isinstance(link, dict):
            continue
        goal_id = str(link.get("goal_id") or "").strip()
        if not goal_id or goal_id not in goal_ids or goal_id in resolved:
            continue
        resolved.append(goal_id)
    return resolved


def _safe_tags(output: dict[str, Any], existing_tags: list[str]) -> list[str]:
    merged: list[str] = []
    for tag in [*existing_tags, *(_string_list(output.get("tags")))]:
        if tag and tag not in merged:
            merged.append(tag)
    return merged[:30]


def _project_id_from_tags(tags: list[str], project_ids: set[str]) -> str | None:
    for tag in tags:
        lowered = str(tag).strip()
        if not lowered.lower().startswith("project:"):
            continue
        project_id = lowered.split(":", 1)[1].strip()
        if project_id and project_id in project_ids:
            return project_id
    return None


def _should_create_improvement(raw_text: str, output: dict[str, Any]) -> bool:
    if bool(output.get("needs_followup")):
        return True
    text = raw_text.lower()
    return "improve" in text or "could be better" in text or "need to fix" in text


def query_entries(
    settings,
    *,
    status: str | None = None,
    entry_type: str | None = None,
    tag: str | None = None,
    goal: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> EntryQueryResult:
    where: list[str] = []
    params: list[Any] = []

    if status:
        where.append("e.status = ?")
        params.append(status)
    if entry_type:
        where.append("e.type = ?")
        params.append(entry_type)
    if tag:
        where.append(
            "EXISTS (SELECT 1 FROM json_each(e.tags_json) jt WHERE CAST(jt.value AS TEXT) = ?)"
        )
        params.append(tag)
    if goal:
        where.append(
            "EXISTS (SELECT 1 FROM json_each(e.goals_json) jg WHERE CAST(jg.value AS TEXT) = ?)"
        )
        params.append(goal)
    if date_from:
        where.append("date(e.created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(e.created_at) <= date(?)")
        params.append(date_to)

    where_sql = f" WHERE {' AND '.join(where)}" if where else ""

    conn = get_connection(settings)
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM entries_index e{where_sql}",
            tuple(params),
        ).fetchone()["c"]

        rows = conn.execute(
            f"""
            SELECT
              e.id,
              e.path,
              e.created_at,
              e.updated_at,
              e.type,
              e.status,
              e.summary,
              e.raw_text,
              e.tags_json,
              e.goals_json
            FROM entries_index e
            {where_sql}
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, int(limit), int(offset)),
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "path": row["path"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "type": row["type"],
                "status": row["status"],
                "summary": row["summary"] or "",
                "raw_text": row["raw_text"] or "",
                "tags": _json_array(row["tags_json"]),
                "goals": _json_array(row["goals_json"]),
            }
        )

    return EntryQueryResult(items=items, total=int(total), limit=int(limit), offset=int(offset))


def process_inbox_entries(
    settings,
    *,
    entry_ids: list[str] | None = None,
    limit: int = 50,
) -> ProcessInboxResult:
    selected = [str(v).strip() for v in (entry_ids or []) if str(v).strip()]
    selected_count = len(selected)

    conn = get_connection(settings)
    try:
        if selected:
            placeholders = ",".join("?" for _ in selected)
            rows = conn.execute(
                f"""
                SELECT id, path
                FROM entries_index
                WHERE status = 'inbox' AND id IN ({placeholders})
                ORDER BY created_at ASC, id ASC
                """,
                tuple(selected),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, path
                FROM entries_index
                WHERE status = 'inbox'
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
    finally:
        conn.close()

    ensure_default_prompt_assets(settings)
    load_prompt_templates(settings)

    manager = VaultManager(settings)
    now_iso = utc_now_iso()
    goals_context, goal_ids = _goal_context(settings)
    projects_context, project_ids = _project_context(settings)
    updated_paths: list[Path] = []
    processed_ids: list[str] = []
    failed_ids: list[str] = []
    missing_paths: list[str] = []
    run_ids: list[str] = []
    observations_indexed = 0
    tasks_synced = 0
    improvements_created = 0

    for row in rows:
        entry_id = str(row["id"])
        path = Path(str(row["path"]))
        if not path.exists():
            missing_paths.append(str(path))
            continue

        parsed = parse_markdown_note(path.read_text(encoding="utf-8"))
        frontmatter = dict(parsed.frontmatter or {})
        raw_text = parsed.sections.get("Context (Raw)", "")
        existing_tags = _string_list(frontmatter.get("tags"))
        existing_goals = _string_list(frontmatter.get("goals"))
        output, used_fallback, preparation_error = _prepare_ingest_output(
            settings,
            raw_text=raw_text,
            created_at=str(frontmatter.get("created") or now_iso),
            fallback_entry_type=_normalize_entry_type(frontmatter.get("type")),
            existing_tags=existing_tags,
            existing_goals=existing_goals,
            goals_context=goals_context,
            goal_ids=goal_ids,
            projects_context=projects_context,
        )

        parse_ok, schema_error = validate_prompt_output_schema(
            settings,
            prompt_id=DEFAULT_PROMPT_ID,
            prompt_version=DEFAULT_PROMPT_VERSION,
            output=output,
        )

        run_id = f"llm-{uuid.uuid4()}"
        run_status = "success" if parse_ok else "failed"
        error_parts: list[str] = []
        if schema_error:
            error_parts.append(f"schema: {schema_error}")
        if preparation_error:
            error_parts.append(f"fallback: {preparation_error}")
        run_error = " | ".join(error_parts) if error_parts else None
        recorded_run_id = record_prompt_run(
            settings,
            prompt_id=DEFAULT_PROMPT_ID,
            prompt_version=DEFAULT_PROMPT_VERSION,
            model=settings.model_ingest,
            status=run_status,
            input_refs=[entry_id, str(path)],
            output=output,
            parse_ok=parse_ok,
            error_text=run_error,
            run_id=run_id,
            actor="local_user",
        )
        run_ids.append(recorded_run_id)

        if not parse_ok:
            failed_ids.append(entry_id)
            continue

        details_md = _render_details_md(output.get("details_bullets"))
        tags = _safe_tags(output, existing_tags)
        resolved_goals = _safe_goal_ids(output, existing_goals, goal_ids)
        entry_type = _normalize_entry_type(output.get("entry_type"), _normalize_entry_type(frontmatter.get("type")))
        output_actions = output.get("actions")
        actions = output_actions if isinstance(output_actions, list) else []
        if entry_type == "todo" or _is_actionable_raw_text(raw_text):
            has_action = any(isinstance(item, dict) and str(item.get("title") or "").strip() for item in actions)
            if not has_action:
                summary_text = str(output.get("summary") or frontmatter.get("summary") or "").strip()
                actions = [_todo_default_action(raw_text, summary_text)]
        actions = _apply_ingest_tool_calls(actions, tool_calls=output.get("tool_calls"), settings=settings)
        if used_fallback:
            actions = _apply_inferred_due_dates(actions, raw_text=raw_text, settings=settings)
        actions_md = _render_actions_md(actions)

        frontmatter["type"] = entry_type
        frontmatter["summary"] = str(output.get("summary") or "").strip() or str(frontmatter.get("summary") or "")
        frontmatter["status"] = "processed"
        frontmatter["updated"] = now_iso
        frontmatter["tags"] = tags
        frontmatter["goals"] = resolved_goals
        updated = render_entry_note(
            frontmatter=frontmatter,
            details=details_md,
            actions=actions_md,
            raw_text=raw_text,
            ai_text=(
                f"Prompt: {DEFAULT_PROMPT_ID}@{DEFAULT_PROMPT_VERSION}\n"
                f"RunId: {recorded_run_id}\n"
                f"ProcessedAt: {now_iso}\n"
                f"Mode: {'fallback' if used_fallback else 'llm'}"
            ),
        )
        manager.atomic_write_text(path, updated)
        updated_paths.append(path)
        processed_ids.append(entry_id)
        observed_at = str(frontmatter.get("created") or now_iso)
        if upsert_activity_observation(
            settings,
            entry_id=entry_id,
            source_run_id=recorded_run_id,
            entry_type=entry_type,
            raw_text=raw_text,
            observed_at=observed_at,
        ):
            observations_indexed += 1
        if upsert_sleep_observation(
            settings,
            entry_id=entry_id,
            source_run_id=recorded_run_id,
            entry_type=entry_type,
            raw_text=raw_text,
        ):
            observations_indexed += 1
        if upsert_food_observation(
            settings,
            entry_id=entry_id,
            source_run_id=recorded_run_id,
            entry_type=entry_type,
            raw_text=raw_text,
        ):
            observations_indexed += 1
        if upsert_weight_observation(
            settings,
            entry_id=entry_id,
            source_run_id=recorded_run_id,
            entry_type=entry_type,
            raw_text=raw_text,
            measured_at=observed_at,
        ):
            observations_indexed += 1

        goal_id = resolved_goals[0] if resolved_goals else None
        project_id = _project_id_from_tags(tags, project_ids)
        task_sync = sync_tasks_from_actions(
            settings,
            entry_id=entry_id,
            source_run_id=recorded_run_id,
            actions_md=actions_md,
            goal_id=goal_id,
            project_id=project_id,
        )
        tasks_synced += int(task_sync["created"]) + int(task_sync["updated"])

        if _should_create_improvement(raw_text, output):
            questions = _string_list(output.get("followup_questions"))
            if questions:
                for question in questions[:2]:
                    create_improvement(
                        settings,
                        title=f"Follow-up: {frontmatter['summary'][:64]}",
                        rationale=question,
                        source_entry_id=entry_id,
                        source_run_id=recorded_run_id,
                        goal_id=goal_id,
                        status="open",
                    )
                    improvements_created += 1
            else:
                create_improvement(
                    settings,
                    title=f"Improve: {frontmatter['summary'][:72]}",
                    rationale=details_md,
                    source_entry_id=entry_id,
                    source_run_id=recorded_run_id,
                    goal_id=goal_id,
                    status="open",
                )
                improvements_created += 1

    if updated_paths:
        VaultIndexer(settings).index_paths(updated_paths)

    return ProcessInboxResult(
        selected_count=selected_count,
        processed_ids=processed_ids,
        failed_ids=failed_ids,
        missing_paths=missing_paths,
        run_ids=run_ids,
        observations_indexed=observations_indexed,
        tasks_synced=tasks_synced,
        improvements_created=improvements_created,
    )
