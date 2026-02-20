from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.llm_config import MODEL_OPTIONS, get_llm_runtime_config, update_llm_runtime_config
from app.services.prompts import list_prompt_templates, load_prompt_templates
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/prompts", tags=["prompts"])


def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _prompt_dir(settings) -> Path:
    return settings.vault_path / "config" / "prompts"


def _relative_prompt_path(path: Path, base: Path) -> str:
    return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")


def _list_prompt_files(settings) -> list[dict[str, str]]:
    base = _prompt_dir(settings)
    base.mkdir(parents=True, exist_ok=True)
    files = sorted(list(base.rglob("*.yaml")) + list(base.rglob("*.yml")))
    items: list[dict[str, str]] = []
    for path in files:
        if "schemas" in path.parts:
            continue
        rel = _relative_prompt_path(path, base)
        prompt_id = path.stem
        version = "-"
        try:
            parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                pid = str(parsed.get("id") or "").strip()
                ver = str(parsed.get("version") or "").strip()
                if pid:
                    prompt_id = pid
                if ver:
                    version = ver
        except Exception:
            pass
        items.append({"file": rel, "prompt_id": prompt_id, "version": version})
    return items


def _resolve_prompt_file(settings, rel_file: str) -> Path:
    base = _prompt_dir(settings).resolve()
    candidate = (base / str(rel_file or "").strip()).resolve()
    if not str(candidate).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid prompt file path.")
    if candidate.suffix.lower() not in {".yaml", ".yml"}:
        raise HTTPException(status_code=400, detail="Prompt file must be YAML.")
    if "schemas" in candidate.parts:
        raise HTTPException(status_code=400, detail="Schema files are not editable here.")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Prompt file not found.")
    return candidate


def _render_editor(settings, *, selected_file: str | None, notice: str | None = None, error: str | None = None) -> str:
    files = _list_prompt_files(settings)
    default_file = selected_file or (files[0]["file"] if files else "")
    content = ""
    if default_file:
        path = _resolve_prompt_file(settings, default_file)
        content = path.read_text(encoding="utf-8")
    return render(
        "fragments/prompt_editor.html",
        files=files,
        selected_file=default_file,
        content=content,
        notice=notice,
        error=error,
    )


@router.get("", response_model=None)
def prompts_list(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    result = list_prompt_templates(settings, limit=limit, offset=offset)
    if wants_html(request):
        return HTMLResponse(render(
            "fragments/prompt_list.html",
            items=result["items"],
            total=result["total"],
        ))
    return result


@router.post("/reload", response_model=None)
def prompts_reload(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    load_result = load_prompt_templates(settings)
    listed = list_prompt_templates(settings, limit=200, offset=0)
    payload = {
        "loaded": load_result.loaded,
        "errors": load_result.errors,
        "total": listed["total"],
        "items": listed["items"],
    }
    if wants_html(request):
        notice = f"Reload complete: loaded={load_result.loaded}, errors={len(load_result.errors)}"
        if load_result.errors:
            first = load_result.errors[0]
            notice += f" First error: {first['path']} -> {first['error']}"
        return HTMLResponse(render(
            "fragments/prompt_list.html",
            items=listed["items"],
            total=listed["total"],
            notice=notice,
        ))
    return payload


@router.get("/llm-config", response_model=None)
def llm_config_get(request: Request) -> Any:
    settings = request.app.state.settings
    payload = get_llm_runtime_config(settings)
    if wants_html(request):
        return HTMLResponse(render(
            "fragments/llm_config.html",
            cfg=payload,
            model_options=MODEL_OPTIONS,
        ))
    return payload


@router.post("/llm-config", response_model=None)
async def llm_config_update(request: Request) -> Any:
    settings = request.app.state.settings
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        model_ingest = str(body.get("model_ingest") or settings.model_ingest)
        model_distill = str(body.get("model_distill") or settings.model_distill)
        model_analysis = str(body.get("model_analysis") or settings.model_analysis)
        openai_base_url = body.get("openai_base_url")
        openai_api_key = body.get("openai_api_key")
        clear_api_key = _truthy(body.get("clear_api_key"))
        persist = _truthy(body.get("persist", True))
    else:
        form = await read_form_body(request)
        model_ingest = str(form_first(form, "model_ingest", str(settings.model_ingest)) or settings.model_ingest)
        model_distill = str(form_first(form, "model_distill", str(settings.model_distill)) or settings.model_distill)
        model_analysis = str(form_first(form, "model_analysis", str(settings.model_analysis)) or settings.model_analysis)
        openai_base_url = form_first(form, "openai_base_url")
        openai_api_key = form_first(form, "openai_api_key")
        clear_api_key = _truthy(form_first(form, "clear_api_key"))
        persist = _truthy(form_first(form, "persist"))

    try:
        updated = update_llm_runtime_config(
            settings,
            model_ingest=model_ingest,
            model_distill=model_distill,
            model_analysis=model_analysis,
            openai_base_url=openai_base_url,
            openai_api_key=openai_api_key,
            clear_api_key=clear_api_key,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if wants_html(request):
        cfg = get_llm_runtime_config(settings)
        notice = "LLM settings saved."
        if persist:
            notice += " Persisted to .env."
        return HTMLResponse(render(
            "fragments/llm_config.html",
            cfg=cfg,
            model_options=MODEL_OPTIONS,
            notice=notice,
        ))
    return {"ok": True, "persisted": persist, "settings": updated}


@router.get("/editor", response_model=None)
def prompt_editor_get(request: Request, file: str | None = Query(default=None)) -> Any:
    settings = request.app.state.settings
    selected = file
    if wants_html(request):
        try:
            return HTMLResponse(_render_editor(settings, selected_file=selected))
        except HTTPException as exc:
            return HTMLResponse(_render_editor(settings, selected_file=None, error=str(exc.detail)))

    files = _list_prompt_files(settings)
    payload: dict[str, Any] = {"files": files}
    if selected:
        path = _resolve_prompt_file(settings, selected)
        payload["file"] = selected
        payload["content"] = path.read_text(encoding="utf-8")
    return payload


@router.post("/editor", response_model=None)
async def prompt_editor_save(request: Request) -> Any:
    settings = request.app.state.settings
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        selected = str(body.get("file") or "").strip()
        content = str(body.get("content") or "")
    else:
        form = await read_form_body(request)
        selected = str(form_first(form, "file", "") or "").strip()
        content = str(form_first(form, "content", "") or "")

    if not selected:
        raise HTTPException(status_code=422, detail="file is required.")
    if not content.strip():
        raise HTTPException(status_code=422, detail="content is required.")

    path = _resolve_prompt_file(settings, selected)
    previous = path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="Prompt YAML root must be an object.")

    required = ("id", "version", "provider", "model", "schema", "system", "user")
    missing = [key for key in required if not str(parsed.get(key) or "").strip()]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {', '.join(missing)}")

    path.write_text(content.replace("\r\n", "\n"), encoding="utf-8")
    load_result = load_prompt_templates(settings)
    current_path = str(path.resolve())
    current_errors = [
        err
        for err in load_result.errors
        if str(Path(str(err.get("path") or "")).resolve()) == current_path
    ]
    if current_errors:
        path.write_text(previous, encoding="utf-8")
        load_prompt_templates(settings)
        first = current_errors[0]
        raise HTTPException(status_code=422, detail=f"Prompt validation failed: {first.get('error')}")

    listed = list_prompt_templates(settings, limit=200, offset=0)
    payload = {
        "ok": True,
        "file": selected,
        "loaded": load_result.loaded,
        "errors": load_result.errors,
        "total": listed["total"],
    }
    if wants_html(request):
        notice = f"Saved {selected} and reloaded prompts."
        if load_result.errors:
            notice += f" Reload had {len(load_result.errors)} warning error(s) from other files."
        return HTMLResponse(_render_editor(settings, selected_file=selected, notice=notice))
    return payload
