from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.core.hashing import PAYLOAD_HASH_VERSION, canonical_payload_hash
from app.core.time import utc_now_iso
from app.db.engine import get_connection
from app.services.goals import goal_dashboard
from app.services.improvements import create_improvement
from app.services.llm import run_openai_json_prompt
from app.services.prompts import (
    CHAT_DISTILL_PROMPT_ID,
    CHAT_DISTILL_PROMPT_VERSION,
    CHAT_RESPONSE_PROMPT_ID,
    CHAT_RESPONSE_PROMPT_VERSION,
)
from app.services.runs import record_prompt_run
from app.services.schema_validation import validate_prompt_output_schema
from app.services.tasks import sync_tasks_from_actions
from app.vault.manager import VaultManager
from app.vault.markdown import dump_frontmatter


def _json_dump(value: Any, default: Any) -> str:
    if value is None:
        value = default
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _ensure_run(conn, run_id: str) -> None:
    conn.execute(
        """
        INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json, created_at)
        VALUES (?, 'manual', 'local_user', '{}', ?)
        ON CONFLICT(run_id) DO NOTHING
        """,
        (run_id, utc_now_iso()),
    )


def _thread_markdown_path(settings, thread_id: str) -> Path:
    return settings.vault_path / "chats" / f"{thread_id}.md"


def _write_thread_markdown(settings, thread: dict[str, Any], messages: list[dict[str, Any]]) -> None:
    fm = {
        "id": thread["thread_id"],
        "logical_id": thread["logical_id"],
        "entity_type": "chat_thread",
        "goal_id": thread.get("goal_id"),
        "source_run_id": thread["source_run_id"],
        "version_no": thread["version_no"],
        "is_current": True,
        "supersedes_id": thread.get("supersedes_id"),
        "created": thread["created_at"],
        "updated": thread["updated_at"],
        "title": thread["title"],
    }
    body = [dump_frontmatter(fm), "\n## Thread Meta\n", f"- Title: {thread['title']}\n"]
    if thread.get("goal_id"):
        body.append(f"- GoalId: {thread['goal_id']}\n")
    body.append("\n## Transcript\n")
    for msg in messages:
        body.append(f"- [{msg['created_at']}] {msg['role']}: {msg['content']}\n")
    text = "".join(body)
    manager = VaultManager(settings)
    manager.atomic_write_text(_thread_markdown_path(settings, thread["thread_id"]), text)


def create_chat_thread(settings, *, title: str, goal_id: str | None = None) -> dict[str, Any]:
    now = utc_now_iso()
    thread_id = f"chat-{uuid.uuid4()}"
    run_id = f"manual-{uuid.uuid4()}"
    conn = get_connection(settings)
    try:
        _ensure_run(conn, run_id)
        conn.execute(
            """
            INSERT INTO chat_threads (
              thread_id, logical_id, path, source_run_id, goal_id, title,
              version_no, is_current, supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, NULL, ?, ?)
            """,
            (
                thread_id,
                thread_id,
                str(_thread_markdown_path(settings, thread_id)),
                run_id,
                goal_id,
                title.strip(),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    thread = get_chat_thread(settings, thread_id)
    if thread:
        _write_thread_markdown(settings, thread, [])
    return thread


def get_chat_thread(settings, thread_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT thread_id, logical_id, path, source_run_id, goal_id, title,
                   version_no, is_current, supersedes_id, created_at, updated_at
            FROM chat_threads
            WHERE thread_id = ?
            """,
            (thread_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "thread_id": row["thread_id"],
        "logical_id": row["logical_id"],
        "path": row["path"],
        "source_run_id": row["source_run_id"],
        "goal_id": row["goal_id"],
        "title": row["title"],
        "version_no": int(row["version_no"]),
        "is_current": bool(row["is_current"]),
        "supersedes_id": row["supersedes_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_chat_threads(settings, *, goal_id: str | None = None) -> list[dict[str, Any]]:
    where = "WHERE is_current = 1"
    params: tuple[Any, ...] = ()
    if goal_id:
        where += " AND goal_id = ?"
        params = (goal_id,)
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            f"""
            SELECT thread_id, goal_id, title, created_at, updated_at
            FROM chat_threads
            {where}
            ORDER BY updated_at DESC, thread_id DESC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "thread_id": row["thread_id"],
            "goal_id": row["goal_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def list_chat_messages(settings, *, thread_id: str) -> list[dict[str, Any]]:
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT message_id, thread_id, role, content, source_run_id, created_at
            FROM chat_messages
            WHERE thread_id = ?
            ORDER BY created_at ASC, message_id ASC
            """,
            (thread_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "message_id": row["message_id"],
            "thread_id": row["thread_id"],
            "role": row["role"],
            "content": row["content"],
            "source_run_id": row["source_run_id"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def add_chat_message(
    settings,
    *,
    thread_id: str,
    role: str,
    content: str,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    run_id = source_run_id or f"manual-{uuid.uuid4()}"
    message_id = f"msg-{uuid.uuid4()}"
    conn = get_connection(settings)
    try:
        exists = conn.execute("SELECT 1 FROM chat_threads WHERE thread_id = ?", (thread_id,)).fetchone()
        if not exists:
            raise KeyError("Thread not found.")
        _ensure_run(conn, run_id)
        conn.execute(
            """
            INSERT INTO chat_messages (message_id, thread_id, role, content, source_run_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, thread_id, role, content.strip(), run_id, now),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE thread_id = ?",
            (now, thread_id),
        )
        conn.commit()
    finally:
        conn.close()

    thread = get_chat_thread(settings, thread_id)
    messages = list_chat_messages(settings, thread_id=thread_id)
    if thread:
        _write_thread_markdown(settings, thread, messages)
    return messages[-1]


def build_chat_context(settings, *, goal_id: str | None = None) -> dict[str, Any]:
    if not goal_id:
        return {"goal": None, "metrics": None, "recent_entries": []}
    dashboard = goal_dashboard(settings, goal_id=goal_id)
    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT e.id, e.summary, e.created_at, e.type
            FROM entries_index e
            JOIN goal_links gl ON gl.entry_id = e.id
            WHERE gl.goal_id = ?
            ORDER BY e.created_at DESC
            LIMIT 10
            """,
            (goal_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "goal": dashboard["goal"] if dashboard else None,
        "metrics": dashboard["metrics"] if dashboard else None,
        "recent_entries": [
            {"id": row["id"], "summary": row["summary"], "created_at": row["created_at"], "type": row["type"]}
            for row in rows
        ],
    }


def _latest_assistant_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            return str(msg["content"] or "")
    return str(messages[-1]["content"] or "") if messages else ""


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg["role"] == "user":
            return str(msg["content"] or "")
    return ""


def _create_insight(settings, *, thread: dict[str, Any], source_run_id: str, title: str, evidence: list[str]) -> str:
    conn = get_connection(settings)
    try:
        insight_id = f"insight-{uuid.uuid4()}"
        logical_id = insight_id
        payload_seed = {
            "logical_id": logical_id,
            "title": title,
            "goal_id": thread.get("goal_id"),
            "evidence": evidence,
        }
        payload_hash = canonical_payload_hash(payload_seed)
        conn.execute(
            """
            INSERT INTO insights (
              insight_id, logical_id, path, source_entry_id, source_run_id, goal_id, title,
              evidence_json, payload_hash, payload_hash_version, version_no, is_current,
              supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, 1, 1, NULL, ?, ?)
            """,
            (
                insight_id,
                logical_id,
                source_run_id,
                thread.get("goal_id"),
                title,
                _json_dump(evidence, []),
                payload_hash,
                PAYLOAD_HASH_VERSION,
                utc_now_iso(),
                utc_now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return insight_id


def _action_lines(actions: Any) -> str:
    if not isinstance(actions, list):
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
        due = str(item.get("due_date") or "").strip()
        suffix = f" due:{due}" if due else ""
        lines.append(f"- [{marker}] {title}{suffix}")
    return "\n".join(lines) if lines else "-"


def _fallback_chat_response(
    *,
    thread: dict[str, Any],
    messages: list[dict[str, Any]],
    context: dict[str, Any],
) -> dict[str, Any]:
    latest_user = _latest_user_text(messages)
    metrics = context.get("metrics") if isinstance(context, dict) else {}
    referenced: list[dict[str, Any]] = []
    if isinstance(metrics, dict):
        for key in ("steps_avg_7d", "sleep_avg_min_7d", "logging_completeness_7d_pct"):
            if metrics.get(key) is None:
                continue
            referenced.append(
                {
                    "metric": key,
                    "label": key.replace("_", " "),
                    "period": "last_7_days",
                    "value": metrics[key],
                }
            )
    actions = [{"title": "Pick one concrete next step for tomorrow.", "priority": "medium"}]
    if latest_user:
        actions = [{"title": latest_user[:180], "priority": "medium"}]

    improvement: dict[str, Any] = {
        "title": "Tighten execution loop",
        "rationale": "Translate the latest coaching point into one measurable daily action.",
        "priority": "medium",
    }
    if thread.get("goal_id"):
        improvement["goal_id"] = str(thread["goal_id"])

    assistant = (
        "Based on your current context, focus on one high-impact action today. "
        "Keep the action specific and easy to complete."
    )
    return {
        "assistant_message": assistant,
        "referenced_data_points": referenced[:30],
        "detected_gaps": [],
        "suggested_actions": actions[:15],
        "recommended_improvements": [improvement],
        "needs_followup": False,
        "followup_questions": [],
        "confidence": 0.55,
    }


def _fallback_distill_output(*, thread: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
    text = _latest_assistant_text(messages)
    lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    if not lines:
        lines = [text[:140] or "Review this thread and define next actions."]

    evidence_rows = []
    for msg in messages[-5:]:
        evidence_rows.append(
            {
                "entry_id": msg["message_id"],
                "note": str(msg["content"] or "")[:280] or "message context",
            }
        )
    if not evidence_rows:
        evidence_rows = [{"entry_id": f"thread-{thread['thread_id']}", "note": "thread summary"}]

    insight: dict[str, Any] = {
        "title": lines[0][:180],
        "evidence": evidence_rows[:20],
        "confidence": 0.6,
    }
    improvement: dict[str, Any] = {
        "title": f"Improve: {lines[0][:120]}",
        "rationale": text[:600] or lines[0],
        "priority": "medium",
    }
    todos: list[dict[str, Any]] = []
    for line in lines[:3]:
        todo: dict[str, Any] = {"title": line[:190], "priority": "medium"}
        if thread.get("goal_id"):
            todo["goal_id"] = str(thread["goal_id"])
        todos.append(todo)

    if thread.get("goal_id"):
        insight["goal_id"] = str(thread["goal_id"])
        improvement["goal_id"] = str(thread["goal_id"])

    output: dict[str, Any] = {
        "thread_id": thread["thread_id"],
        "summary": lines[0][:480],
        "insights": [insight],
        "improvements": [improvement],
        "todos": todos or [{"title": "Review chat outcomes.", "priority": "medium"}],
        "confidence": 0.55,
    }
    if thread.get("goal_id"):
        output["goal_id"] = str(thread["goal_id"])
    return output


def generate_thread_reply(settings, *, thread_id: str) -> dict[str, Any]:
    thread = get_chat_thread(settings, thread_id)
    if not thread:
        raise KeyError("Thread not found.")
    messages = list_chat_messages(settings, thread_id=thread_id)
    if not messages:
        raise ValueError("Thread has no messages.")

    context = build_chat_context(settings, goal_id=thread.get("goal_id"))
    fallback_output = _fallback_chat_response(thread=thread, messages=messages, context=context)
    llm_error: str | None = None
    used_fallback = False
    output: dict[str, Any]
    try:
        output = run_openai_json_prompt(
            settings,
            prompt_id=CHAT_RESPONSE_PROMPT_ID,
            prompt_version=CHAT_RESPONSE_PROMPT_VERSION,
            model_override=settings.model_analysis,
            variables={
                "goal_context_json": _json_dump(context, {}),
                "messages_json": _json_dump(
                    [{"message_id": m["message_id"], "role": m["role"], "content": m["content"]} for m in messages[-30:]],
                    [],
                ),
            },
        )
    except Exception as exc:
        used_fallback = True
        llm_error = str(exc)
        output = fallback_output

    parse_ok, schema_error = validate_prompt_output_schema(
        settings,
        prompt_id=CHAT_RESPONSE_PROMPT_ID,
        prompt_version=CHAT_RESPONSE_PROMPT_VERSION,
        output=output,
    )
    if not parse_ok:
        used_fallback = True
        output = fallback_output
        parse_ok, schema_error = validate_prompt_output_schema(
            settings,
            prompt_id=CHAT_RESPONSE_PROMPT_ID,
            prompt_version=CHAT_RESPONSE_PROMPT_VERSION,
            output=output,
        )

    run_error = None
    if schema_error:
        run_error = f"schema: {schema_error}"
    if llm_error:
        run_error = f"{run_error} | llm: {llm_error}" if run_error else f"llm: {llm_error}"
    run_id = record_prompt_run(
        settings,
        prompt_id=CHAT_RESPONSE_PROMPT_ID,
        prompt_version=CHAT_RESPONSE_PROMPT_VERSION,
        model=settings.model_analysis,
        status="success" if parse_ok else "failed",
        input_refs=[thread_id],
        output=output,
        parse_ok=parse_ok,
        error_text=run_error,
    )
    if not parse_ok:
        raise ValueError(f"Chat reply schema validation failed: {schema_error}")

    assistant_text = str(output.get("assistant_message") or "").strip()
    followups = output.get("followup_questions") if isinstance(output.get("followup_questions"), list) else []
    if followups and bool(output.get("needs_followup")):
        assistant_text += "\n\nFollow-up:\n" + "\n".join(f"- {str(question).strip()}" for question in followups[:3] if str(question).strip())
    if not assistant_text:
        raise ValueError("Chat reply output did not include assistant_message.")

    saved = add_chat_message(
        settings,
        thread_id=thread_id,
        role="assistant",
        content=assistant_text,
        source_run_id=run_id,
    )

    actions_md = _action_lines(output.get("suggested_actions"))
    task_count = 0
    if actions_md != "-":
        task_sync = sync_tasks_from_actions(
            settings,
            entry_id=f"chat-thread-{thread_id}",
            source_run_id=run_id,
            actions_md=actions_md,
            goal_id=thread.get("goal_id"),
        )
        task_count = int(task_sync["created"]) + int(task_sync["updated"])

    improvements_created = 0
    improvements = output.get("recommended_improvements") if isinstance(output.get("recommended_improvements"), list) else []
    for item in improvements[:2]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        if not title or not rationale:
            continue
        create_improvement(
            settings,
            title=title[:180],
            rationale=rationale[:760],
            source_entry_id=None,
            source_run_id=run_id,
            goal_id=thread.get("goal_id"),
            status="open",
        )
        improvements_created += 1

    return {
        "thread_id": thread_id,
        "source_run_id": run_id,
        "message_id": saved["message_id"],
        "assistant_message": saved["content"],
        "tasks_created_or_updated": task_count,
        "improvements_created": improvements_created,
        "used_fallback": used_fallback,
    }


def distill_chat_outcomes(settings, *, thread_id: str) -> dict[str, Any]:
    thread = get_chat_thread(settings, thread_id)
    if not thread:
        raise KeyError("Thread not found.")
    messages = list_chat_messages(settings, thread_id=thread_id)
    if not messages:
        raise ValueError("Thread has no messages.")

    fallback_output = _fallback_distill_output(thread=thread, messages=messages)
    llm_error: str | None = None
    used_fallback = False
    output: dict[str, Any]
    try:
        output = run_openai_json_prompt(
            settings,
            prompt_id=CHAT_DISTILL_PROMPT_ID,
            prompt_version=CHAT_DISTILL_PROMPT_VERSION,
            model_override=settings.model_analysis,
            variables={
                "thread_id": thread_id,
                "goal_id": str(thread.get("goal_id") or ""),
                "messages_json": _json_dump(
                    [{"message_id": m["message_id"], "role": m["role"], "content": m["content"]} for m in messages[-60:]],
                    [],
                ),
            },
        )
    except Exception as exc:
        used_fallback = True
        llm_error = str(exc)
        output = fallback_output

    parse_ok, schema_error = validate_prompt_output_schema(
        settings,
        prompt_id=CHAT_DISTILL_PROMPT_ID,
        prompt_version=CHAT_DISTILL_PROMPT_VERSION,
        output=output,
    )
    if not parse_ok:
        used_fallback = True
        output = fallback_output
        parse_ok, schema_error = validate_prompt_output_schema(
            settings,
            prompt_id=CHAT_DISTILL_PROMPT_ID,
            prompt_version=CHAT_DISTILL_PROMPT_VERSION,
            output=output,
        )

    run_error = None
    if schema_error:
        run_error = f"schema: {schema_error}"
    if llm_error:
        run_error = f"{run_error} | llm: {llm_error}" if run_error else f"llm: {llm_error}"
    source_run_id = record_prompt_run(
        settings,
        prompt_id=CHAT_DISTILL_PROMPT_ID,
        prompt_version=CHAT_DISTILL_PROMPT_VERSION,
        model=settings.model_analysis,
        status="success" if parse_ok else "failed",
        input_refs=[thread_id],
        output=output,
        parse_ok=parse_ok,
        error_text=run_error,
    )
    if not parse_ok:
        raise ValueError(f"Distill schema validation failed: {schema_error}")

    insight_ids: list[str] = []
    for insight in output.get("insights") or []:
        if not isinstance(insight, dict):
            continue
        title = str(insight.get("title") or "").strip()
        if not title:
            continue
        evidence_notes: list[str] = []
        for evidence in insight.get("evidence") or []:
            if not isinstance(evidence, dict):
                continue
            note = str(evidence.get("note") or "").strip()
            if note:
                evidence_notes.append(note)
        if not evidence_notes:
            evidence_notes = [str(output.get("summary") or "").strip()[:220] or "chat summary"]
        insight_ids.append(
            _create_insight(
                settings,
                thread=thread,
                source_run_id=source_run_id,
                title=title[:180],
                evidence=evidence_notes[:8],
            )
        )

    improvement_ids: list[str] = []
    for item in (output.get("improvements") or [])[:3]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        if not title or not rationale:
            continue
        improvement = create_improvement(
            settings,
            title=title[:180],
            rationale=rationale[:900],
            source_entry_id=None,
            source_run_id=source_run_id,
            goal_id=thread.get("goal_id"),
            status="open",
        )
        improvement_ids.append(improvement["improvement_id"])

    actions_md = _action_lines(output.get("todos"))
    task_count = 0
    if actions_md != "-":
        task_sync = sync_tasks_from_actions(
            settings,
            entry_id=f"chat-thread-{thread_id}",
            source_run_id=source_run_id,
            actions_md=actions_md,
            goal_id=thread.get("goal_id"),
        )
        task_count = int(task_sync["created"]) + int(task_sync["updated"])

    return {
        "thread_id": thread_id,
        "source_run_id": source_run_id,
        "insight_id": insight_ids[0] if insight_ids else "",
        "improvement_id": improvement_ids[0] if improvement_ids else "",
        "insight_ids": insight_ids,
        "improvement_ids": improvement_ids,
        "tasks_created_or_updated": task_count,
        "used_fallback": used_fallback,
    }
