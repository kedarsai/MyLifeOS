from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.db.engine import get_connection


@dataclass
class PromptLoadResult:
    loaded: int
    errors: list[dict[str, str]]


INGEST_PROMPT_ID = "ingest_extract"
INGEST_PROMPT_VERSION = "v1"
CHAT_RESPONSE_PROMPT_ID = "goal_chat_response"
CHAT_RESPONSE_PROMPT_VERSION = "v1"
CHAT_DISTILL_PROMPT_ID = "chat_distill_outcomes"
CHAT_DISTILL_PROMPT_VERSION = "v1"
WEEKLY_REVIEW_PROMPT_ID = "weekly_goal_review"
WEEKLY_REVIEW_PROMPT_VERSION = "v1"
ENTITY_CHAT_PROMPT_ID = "entity_chat_response"
ENTITY_CHAT_PROMPT_VERSION = "v1"

# Backward compatibility for existing imports.
DEFAULT_PROMPT_ID = INGEST_PROMPT_ID
DEFAULT_PROMPT_VERSION = INGEST_PROMPT_VERSION

DEFAULT_INGEST_PROMPT_TEXT = """id: ingest_extract
version: v1
provider: openai
model: gpt-5-mini
params:
  verbosity: low
  max_output_tokens: 900
schema: schemas/ingest_extract.json
system: |
  You are a personal life OS extraction model.
  Convert one raw captured note into structured JSON.
  Pick entry_type carefully, keep summary concise, and extract concrete tasks.
  When task timing is relative (for example: today, tomorrow, tonight, EOD, ASAP),
  add a `tool_calls` item using `resolve_relative_due_date` with:
  - `action_index`: index of the target action in `actions`
  - `offset_days`: 0 for today/tonight/EOD/ASAP today, 1 for tomorrow, etc.
  Use `set_due_date` only for explicit absolute dates not already in action `due_date`.
  For project assignment: when relevant, include a tag in the form project:<project_id>.
  Only use goal ids and project ids provided in context.
user: |
  Raw entry:
  {{raw_text}}

  Existing tags:
  {{existing_tags_json}}

  Available goals:
  {{goals_context_json}}

  Available projects:
  {{projects_context_json}}

  Created timestamp:
  {{created_at}}
"""

DEFAULT_CHAT_RESPONSE_PROMPT_TEXT = """id: goal_chat_response
version: v1
provider: openai
model: gpt-5.2
params:
  reasoning_effort: none
  temperature: 0.3
  verbosity: medium
  max_output_tokens: 900
schema: schemas/goal_chat_response.json
system: |
  You are a goal coach. Use provided metrics and recent entries.
  Give specific, actionable responses tied to the user's data.
user: |
  Goal context:
  {{goal_context_json}}

  Conversation messages:
  {{messages_json}}
"""

DEFAULT_CHAT_DISTILL_PROMPT_TEXT = """id: chat_distill_outcomes
version: v1
provider: openai
model: gpt-5.2
params:
  reasoning_effort: none
  temperature: 0.2
  verbosity: low
  max_output_tokens: 800
schema: schemas/chat_distill_outcomes.json
system: |
  Distill a goal-chat thread into durable insights, improvements, and todos.
  Keep outputs specific and tied to message evidence.
user: |
  Thread id: {{thread_id}}
  Goal id: {{goal_id}}

  Messages:
  {{messages_json}}
"""

DEFAULT_ENTITY_CHAT_PROMPT_TEXT = """id: entity_chat_response
version: v1
provider: openai
model: gpt-5.2
params:
  reasoning_effort: none
  temperature: 0.3
  verbosity: medium
  max_output_tokens: 3000
schema: schemas/entity_chat_response.json
system: |
  You are a knowledge coach. You help users think through their ideas,
  explore thought topics, and make progress on goals.
  Use provided entity context, insight cards, and recent entries.
  Give specific, actionable responses tied to the user's data.
  When appropriate, suggest concrete actions via proposed_actions.
  All write actions must have requires_confirmation: true.
  Available action_type values: create_task, create_improvement, save_card,
  update_idea_status, convert_idea.
user: |
  Entity context:
  {{entity_context_json}}

  Recent insight cards:
  {{cards_context_json}}

  Conversation messages:
  {{messages_json}}
"""

DEFAULT_WEEKLY_REVIEW_PROMPT_TEXT = """id: weekly_goal_review
version: v1
provider: openai
model: gpt-5.2
params:
  reasoning_effort: none
  temperature: 0.2
  verbosity: low
  max_output_tokens: 900
schema: schemas/weekly_goal_review.json
system: |
  You are a local-first life assistant producing concise, actionable weekly coaching.
  Keep output grounded in deterministic metrics and missing-data signals.
user: |
  Weekly input:
  {{goal_context_json}}
"""


def _json_dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _ensure_schema_from_repo(schema_dir: Path, *, target_name: str, source_name: str) -> None:
    target = schema_dir / target_name
    if target.exists():
        return
    project_schema = Path(__file__).resolve().parents[2] / "schemas" / source_name
    if project_schema.exists():
        target.write_text(project_schema.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        target.write_text('{"type":"object","additionalProperties":true}', encoding="utf-8")


def ensure_default_prompt_assets(settings) -> None:
    base = settings.vault_path / "config" / "prompts"
    schema_dir = base / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    base.mkdir(parents=True, exist_ok=True)

    _ensure_schema_from_repo(schema_dir, target_name="ingest_extract.json", source_name="ingest_extract.json")
    _ensure_schema_from_repo(schema_dir, target_name="goal_chat_response.json", source_name="goal_chat_response.json")
    _ensure_schema_from_repo(schema_dir, target_name="chat_distill_outcomes.json", source_name="distill_outcomes.json")
    _ensure_schema_from_repo(schema_dir, target_name="weekly_goal_review.json", source_name="weekly_goal_review.json")
    _ensure_schema_from_repo(schema_dir, target_name="entity_chat_response.json", source_name="entity_chat_response.json")

    assets = [
        (base / "ingest_extract.yaml", DEFAULT_INGEST_PROMPT_TEXT),
        (base / "goal_chat_response.yaml", DEFAULT_CHAT_RESPONSE_PROMPT_TEXT),
        (base / "chat_distill_outcomes.yaml", DEFAULT_CHAT_DISTILL_PROMPT_TEXT),
        (base / "weekly_goal_review.yaml", DEFAULT_WEEKLY_REVIEW_PROMPT_TEXT),
        (base / "entity_chat_response.yaml", DEFAULT_ENTITY_CHAT_PROMPT_TEXT),
    ]
    for path, text in assets:
        if not path.exists():
            path.write_text(text, encoding="utf-8")


def _load_schema_json(path: Path, raw_schema: Any) -> str:
    if isinstance(raw_schema, dict):
        return _json_dump(raw_schema)
    if isinstance(raw_schema, str):
        schema_path = (path.parent / raw_schema).resolve()
        if not schema_path.exists():
            raise ValueError(f"Schema file not found: {schema_path}")
        try:
            parsed = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid schema JSON: {schema_path}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Schema JSON must be an object: {schema_path}")
        return _json_dump(parsed)
    raise ValueError("schema must be a JSON object or relative JSON file path")


def _parse_prompt_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Prompt YAML root must be an object")

    prompt_id = str(raw.get("id") or "").strip()
    version = str(raw.get("version") or "").strip()
    provider = str(raw.get("provider") or "").strip()
    model = str(raw.get("model") or "").strip()
    system_text = str(raw.get("system") or "")
    user_text = str(raw.get("user") or "")
    params = raw.get("params") or {}
    schema = raw.get("schema")

    if not prompt_id:
        raise ValueError("Missing required field: id")
    if not version:
        raise ValueError("Missing required field: version")
    if not provider:
        raise ValueError("Missing required field: provider")
    if not model:
        raise ValueError("Missing required field: model")
    if not system_text.strip():
        raise ValueError("Missing required field: system")
    if not user_text.strip():
        raise ValueError("Missing required field: user")
    if not isinstance(params, dict):
        raise ValueError("params must be an object")

    return {
        "prompt_id": prompt_id,
        "name": str(raw.get("name") or prompt_id),
        "version": version,
        "provider": provider,
        "model": model,
        "params_json": _json_dump(params),
        "system_text": system_text,
        "user_text": user_text,
        "schema_json": _load_schema_json(path, schema),
    }


def load_prompt_templates(settings) -> PromptLoadResult:
    prompt_dir = settings.vault_path / "config" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_files = sorted(list(prompt_dir.rglob("*.yaml")) + list(prompt_dir.rglob("*.yml")))

    conn = get_connection(settings)
    loaded = 0
    errors: list[dict[str, str]] = []
    try:
        for path in prompt_files:
            try:
                parsed = _parse_prompt_yaml(path)
                conn.execute(
                    """
                    INSERT INTO prompt_templates (
                      prompt_id, name, version, provider, model, params_json, system_text, user_text, schema_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(prompt_id, version) DO UPDATE SET
                      name=excluded.name,
                      provider=excluded.provider,
                      model=excluded.model,
                      params_json=excluded.params_json,
                      system_text=excluded.system_text,
                      user_text=excluded.user_text,
                      schema_json=excluded.schema_json
                    """,
                    (
                        parsed["prompt_id"],
                        parsed["name"],
                        parsed["version"],
                        parsed["provider"],
                        parsed["model"],
                        parsed["params_json"],
                        parsed["system_text"],
                        parsed["user_text"],
                        parsed["schema_json"],
                    ),
                )
                loaded += 1
            except Exception as exc:
                errors.append({"path": str(path), "error": str(exc)})
        conn.commit()
    finally:
        conn.close()
    return PromptLoadResult(loaded=loaded, errors=errors)


def list_prompt_templates(settings, *, limit: int = 200, offset: int = 0) -> dict[str, Any]:
    conn = get_connection(settings)
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM prompt_templates").fetchone()["c"]
        rows = conn.execute(
            """
            SELECT
              prompt_id,
              name,
              version,
              provider,
              model,
              params_json,
              created_at
            FROM prompt_templates
            ORDER BY prompt_id ASC, version DESC
            LIMIT ? OFFSET ?
            """,
            (int(limit), int(offset)),
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in rows:
        try:
            params = json.loads(row["params_json"] or "{}")
        except json.JSONDecodeError:
            params = {}
        items.append(
            {
                "prompt_id": row["prompt_id"],
                "name": row["name"],
                "version": row["version"],
                "provider": row["provider"],
                "model": row["model"],
                "params": params,
                "created_at": row["created_at"],
            }
        )
    return {"items": items, "total": int(total), "limit": int(limit), "offset": int(offset)}
