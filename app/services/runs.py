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
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def record_prompt_run(
    settings,
    *,
    prompt_id: str,
    prompt_version: str,
    model: str | None,
    status: str,
    input_refs: list[str] | None = None,
    output: dict[str, Any] | None = None,
    parse_ok: bool = False,
    error_text: str | None = None,
    actor: str = "local_user",
    run_id: str | None = None,
    parent_run_id: str | None = None,
    notes: dict[str, Any] | None = None,
) -> str:
    if status not in {"pending", "success", "failed"}:
        raise ValueError(f"Unsupported run status: {status}")

    now = utc_now_iso()
    final_run_id = run_id or f"llm-{uuid.uuid4()}"
    completed_at = now if status in {"success", "failed"} else None

    conn = get_connection(settings)
    try:
        exists = conn.execute(
            """
            SELECT 1
            FROM prompt_templates
            WHERE prompt_id = ? AND version = ?
            """,
            (prompt_id, prompt_version),
        ).fetchone()
        if not exists:
            raise ValueError(f"Prompt template not found: {prompt_id}@{prompt_version}")

        conn.execute(
            """
            INSERT INTO artifact_runs (run_id, run_kind, actor, parent_run_id, notes_json, created_at)
            VALUES (?, 'llm', ?, ?, ?, ?)
            ON CONFLICT(run_id) DO NOTHING
            """,
            (final_run_id, actor, parent_run_id, _json_dump(notes, {}), now),
        )

        conn.execute(
            """
            INSERT INTO prompt_runs (
              run_id, prompt_id, prompt_version, model, created_at, completed_at, status,
              input_refs_json, output_json, parse_ok, error_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
              prompt_id=excluded.prompt_id,
              prompt_version=excluded.prompt_version,
              model=excluded.model,
              completed_at=excluded.completed_at,
              status=excluded.status,
              input_refs_json=excluded.input_refs_json,
              output_json=excluded.output_json,
              parse_ok=excluded.parse_ok,
              error_text=excluded.error_text
            """,
            (
                final_run_id,
                prompt_id,
                prompt_version,
                model,
                now,
                completed_at,
                status,
                _json_dump(input_refs, []),
                _json_dump(output, None) if output is not None else None,
                1 if parse_ok else 0,
                error_text,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return final_run_id


def list_prompt_runs(
    settings,
    *,
    status: str | None = None,
    prompt_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if status:
        where.append("r.status = ?")
        params.append(status)
    if prompt_id:
        where.append("r.prompt_id = ?")
        params.append(prompt_id)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    conn = get_connection(settings)
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM prompt_runs r {where_sql}",
            tuple(params),
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT
              r.run_id,
              r.prompt_id,
              r.prompt_version,
              r.model,
              r.created_at,
              r.completed_at,
              r.status,
              r.input_refs_json,
              r.parse_ok,
              r.error_text
            FROM prompt_runs r
            {where_sql}
            ORDER BY r.created_at DESC, r.run_id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, int(limit), int(offset)),
        ).fetchall()
    finally:
        conn.close()

    items = [
        {
            "run_id": row["run_id"],
            "prompt_id": row["prompt_id"],
            "prompt_version": row["prompt_version"],
            "model": row["model"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
            "status": row["status"],
            "input_refs": _json_load(row["input_refs_json"], []),
            "parse_ok": bool(row["parse_ok"]),
            "error_text": row["error_text"],
        }
        for row in rows
    ]
    return {"items": items, "total": int(total), "limit": int(limit), "offset": int(offset)}


def get_prompt_run(settings, run_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT
              r.run_id,
              r.prompt_id,
              r.prompt_version,
              r.model,
              r.created_at,
              r.completed_at,
              r.status,
              r.input_refs_json,
              r.output_json,
              r.parse_ok,
              r.error_text,
              a.parent_run_id,
              a.notes_json
            FROM prompt_runs r
            JOIN artifact_runs a ON a.run_id = r.run_id
            WHERE r.run_id = ?
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "run_id": row["run_id"],
        "prompt_id": row["prompt_id"],
        "prompt_version": row["prompt_version"],
        "model": row["model"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "status": row["status"],
        "input_refs": _json_load(row["input_refs_json"], []),
        "output": _json_load(row["output_json"], None),
        "parse_ok": bool(row["parse_ok"]),
        "error_text": row["error_text"],
        "parent_run_id": row["parent_run_id"],
        "notes": _json_load(row["notes_json"], {}),
    }


def retry_prompt_run(
    settings,
    *,
    source_run_id: str,
    actor: str = "local_user",
) -> str:
    source = get_prompt_run(settings, source_run_id)
    if not source:
        raise KeyError("Source run not found.")
    output = source["output"]
    if output is None:
        raise ValueError("Source run has no output JSON to retry.")

    from app.services.schema_validation import validate_prompt_output_schema

    parse_ok, validation_error = validate_prompt_output_schema(
        settings,
        prompt_id=source["prompt_id"],
        prompt_version=source["prompt_version"],
        output=output,
    )
    status = "success" if parse_ok else "failed"
    error_text = f"schema: {validation_error}" if validation_error else None
    return record_prompt_run(
        settings,
        prompt_id=source["prompt_id"],
        prompt_version=source["prompt_version"],
        model=source["model"],
        status=status,
        input_refs=source["input_refs"],
        output=output,
        parse_ok=parse_ok,
        error_text=error_text,
        actor=actor,
        parent_run_id=source_run_id,
        notes={"retry_of": source_run_id},
    )
