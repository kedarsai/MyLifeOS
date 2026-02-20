from __future__ import annotations

import re
from pathlib import Path


MODEL_OPTIONS = ("gpt-5-mini", "gpt-5.2")

_ENV_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    tail = value[-4:] if len(value) >= 4 else value
    return f"...{tail}"


def _env_encode(value: str) -> str:
    safe = value.replace("\r", "").replace("\n", "")
    if not safe:
        return ""
    if any(ch.isspace() for ch in safe) or "#" in safe or '"' in safe or "'" in safe:
        escaped = safe.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return safe


def _upsert_env_file(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    seen: set[str] = set()

    for line in lines:
        match = _ENV_KEY_RE.match(line)
        if not match:
            out.append(line)
            continue
        key = match.group(1)
        if key not in updates:
            out.append(line)
            continue
        out.append(f"{key}={_env_encode(updates[key])}")
        seen.add(key)

    for key, value in updates.items():
        if key in seen:
            continue
        out.append(f"{key}={_env_encode(value)}")

    text = "\n".join(out)
    if out:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _normalize_model(value: str, *, field_name: str) -> str:
    model = (value or "").strip()
    if not model:
        raise ValueError(f"{field_name} is required.")
    if len(model) > 200:
        raise ValueError(f"{field_name} is too long.")
    return model


def get_llm_runtime_config(settings) -> dict[str, str | bool]:
    api_key = str(settings.openai_api_key or "").strip()
    return {
        "model_ingest": str(settings.model_ingest or "").strip(),
        "model_distill": str(settings.model_distill or "").strip(),
        "model_analysis": str(settings.model_analysis or "").strip(),
        "openai_base_url": str(settings.openai_base_url or "").strip(),
        "openai_api_key_configured": bool(api_key),
        "openai_api_key_preview": _mask_secret(api_key),
    }


def update_llm_runtime_config(
    settings,
    *,
    model_ingest: str,
    model_distill: str,
    model_analysis: str,
    openai_base_url: str | None = None,
    openai_api_key: str | None = None,
    clear_api_key: bool = False,
    persist: bool = True,
    env_path: Path | None = None,
) -> dict[str, str | bool]:
    next_ingest = _normalize_model(model_ingest, field_name="model_ingest")
    next_distill = _normalize_model(model_distill, field_name="model_distill")
    next_analysis = _normalize_model(model_analysis, field_name="model_analysis")
    next_base_url = (openai_base_url or "").strip()
    next_key = (openai_api_key or "").strip()

    settings.model_ingest = next_ingest
    settings.model_distill = next_distill
    settings.model_analysis = next_analysis
    settings.openai_base_url = next_base_url or None
    if clear_api_key:
        settings.openai_api_key = ""
    elif next_key:
        settings.openai_api_key = next_key

    if persist:
        target = env_path or (Path.cwd() / ".env")
        updates = {
            "LIFEOS_MODEL_INGEST": next_ingest,
            "LIFEOS_MODEL_DISTILL": next_distill,
            "LIFEOS_MODEL_ANALYSIS": next_analysis,
            "OPENAI_BASE_URL": next_base_url,
        }
        if clear_api_key:
            updates["OPENAI_API_KEY"] = ""
        elif next_key:
            updates["OPENAI_API_KEY"] = next_key
        _upsert_env_file(target, updates)

    return get_llm_runtime_config(settings)
