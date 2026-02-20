from __future__ import annotations

import json
import re
from typing import Any

from app.db.engine import get_connection


_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_VALID_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high"}
_VALID_VERBOSITY_LEVELS = {"low", "medium", "high"}


def llm_enabled(settings) -> bool:
    return bool((settings.openai_api_key or "").strip())


def _render_template(text: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        value = variables.get(key, "")
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=True)
        return str(value)

    return _VAR_RE.sub(replace, text or "")


def _load_prompt(settings, *, prompt_id: str, prompt_version: str) -> dict[str, Any]:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT prompt_id, version, provider, model, params_json, system_text, user_text, schema_json
            FROM prompt_templates
            WHERE prompt_id = ? AND version = ?
            """,
            (prompt_id, prompt_version),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError(f"Prompt template not found: {prompt_id}@{prompt_version}")
    if str(row["provider"]).strip().lower() != "openai":
        raise ValueError(f"Unsupported provider: {row['provider']}")
    try:
        params = json.loads(row["params_json"] or "{}")
    except json.JSONDecodeError:
        params = {}
    try:
        schema = json.loads(row["schema_json"] or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Prompt schema_json is invalid JSON.") from exc
    return {
        "prompt_id": row["prompt_id"],
        "version": row["version"],
        "model": row["model"],
        "params": params,
        "schema": schema,
        "system_text": row["system_text"] or "",
        "user_text": row["user_text"] or "",
    }


def _pick_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_response_text(response: Any) -> str:
    output_text = _pick_value(response, "output_text", "")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = _pick_value(response, "output", None)
    if not isinstance(output, list):
        return ""

    chunks: list[str] = []
    for item in output:
        content = _pick_value(item, "content", None)
        if not isinstance(content, list):
            continue
        for part in content:
            part_type = str(_pick_value(part, "type", "")).strip().lower()
            if part_type not in {"output_text", "text"}:
                continue
            text = _pick_value(part, "text", "")
            if isinstance(text, str) and text.strip():
                chunks.append(text)
    return "\n".join(chunks).strip()


def _normalize_choice(value: Any, *, allowed: set[str]) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized or normalized not in allowed:
        return None
    return normalized


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _supports_sampling_controls(*, model: str, reasoning_effort: str | None) -> bool:
    normalized_model = (model or "").strip().lower()
    if normalized_model.startswith("gpt-5.2") or normalized_model.startswith("gpt-5.1"):
        effort = (reasoning_effort or "none").strip().lower()
        return effort in {"", "none"}
    if normalized_model.startswith("gpt-5"):
        return False
    return True


def _apply_openai_model_params(
    request_payload: dict[str, Any],
    *,
    params: dict[str, Any],
    model: str,
) -> None:
    reasoning_effort = _normalize_choice(
        params.get("reasoning_effort"),
        allowed=_VALID_REASONING_EFFORTS,
    )
    if reasoning_effort:
        request_payload["reasoning"] = {"effort": reasoning_effort}

    verbosity = _normalize_choice(params.get("verbosity"), allowed=_VALID_VERBOSITY_LEVELS)
    if verbosity:
        text_payload = request_payload.get("text")
        if isinstance(text_payload, dict):
            text_payload["verbosity"] = verbosity

    max_output_tokens = _to_positive_int(params.get("max_output_tokens"))
    if max_output_tokens is not None:
        request_payload["max_output_tokens"] = max_output_tokens

    if _supports_sampling_controls(model=model, reasoning_effort=reasoning_effort):
        temperature = _to_float(params.get("temperature"))
        if temperature is not None:
            request_payload["temperature"] = temperature
        top_p = _to_float(params.get("top_p"))
        if top_p is not None:
            request_payload["top_p"] = top_p


def run_openai_json_prompt(
    settings,
    *,
    prompt_id: str,
    prompt_version: str,
    variables: dict[str, Any],
    model_override: str | None = None,
) -> dict[str, Any]:
    if not llm_enabled(settings):
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    prompt = _load_prompt(settings, prompt_id=prompt_id, prompt_version=prompt_version)
    system_text = _render_template(prompt["system_text"], variables)
    user_text = _render_template(prompt["user_text"], variables)
    model = model_override or str(prompt["model"])
    params = prompt["params"] if isinstance(prompt["params"], dict) else {}

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("openai package is not installed.") from exc

    client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    client = OpenAI(**client_kwargs)

    request_payload: dict[str, Any] = {
        "model": model,
        "input": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": f"{prompt_id}_{prompt_version}".replace("-", "_"),
                "strict": True,
                "schema": prompt["schema"],
            }
        },
    }
    _apply_openai_model_params(request_payload, params=params, model=model)

    resp = client.responses.create(**request_payload)
    content = _extract_response_text(resp)
    if not content:
        raise RuntimeError("LLM returned empty response content.")
    try:
        output = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM returned non-JSON content.") from exc
    if not isinstance(output, dict):
        raise RuntimeError("LLM output must be a JSON object.")
    return output
