from __future__ import annotations

import json
from typing import Any

from jsonschema import ValidationError
from jsonschema.validators import Draft202012Validator

from app.db.engine import get_connection


def validate_prompt_output_schema(
    settings,
    *,
    prompt_id: str,
    prompt_version: str,
    output: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT schema_json
            FROM prompt_templates
            WHERE prompt_id = ? AND version = ?
            """,
            (prompt_id, prompt_version),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return False, f"Prompt template not found: {prompt_id}@{prompt_version}"
    if output is None:
        return False, "Output JSON is required for schema validation."

    try:
        schema = json.loads(row["schema_json"])
    except json.JSONDecodeError:
        return False, "Stored schema_json is invalid JSON."
    if not isinstance(schema, dict):
        return False, "Stored schema_json must be a JSON object."

    validator = Draft202012Validator(schema)
    try:
        validator.validate(output)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        path_text = path if path else "$"
        return False, f"{path_text}: {exc.message}"
    return True, None
