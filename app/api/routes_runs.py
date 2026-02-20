from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.runs import get_prompt_run, list_prompt_runs, record_prompt_run, retry_prompt_run
from app.services.schema_validation import validate_prompt_output_schema
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunLogRequest(BaseModel):
    prompt_id: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    status: str = Field(pattern="^(pending|success|failed)$")
    input_refs: list[str] = Field(default_factory=list)
    output: dict[str, Any] | None = None
    parse_ok: bool = False
    validate_schema: bool = True
    error_text: str | None = Field(default=None, max_length=8000)
    actor: str = Field(default="local_user", min_length=1, max_length=120)
    run_id: str | None = Field(default=None, min_length=1, max_length=200)


class RetryRunRequest(BaseModel):
    actor: str = Field(default="local_user", min_length=1, max_length=120)


def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


@router.get("", response_model=None)
def runs_list(
    request: Request,
    status: str | None = Query(default=None),
    prompt_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    result = list_prompt_runs(settings, status=status, prompt_id=prompt_id, limit=limit, offset=offset)
    if wants_html(request):
        return HTMLResponse(render(
            "fragments/runs_list.html",
            items=result["items"],
            total=result["total"],
        ))
    return result


@router.post("/log", response_model=None)
def log_run(request: Request, payload: RunLogRequest) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    status = payload.status
    parse_ok = payload.parse_ok
    error_text = payload.error_text

    if payload.validate_schema:
        parse_ok, validation_error = validate_prompt_output_schema(
            settings,
            prompt_id=payload.prompt_id,
            prompt_version=payload.prompt_version,
            output=payload.output,
        )
        if validation_error:
            if error_text:
                error_text = f"{error_text} | schema: {validation_error}"
            else:
                error_text = f"schema: {validation_error}"
        if status == "success" and not parse_ok:
            status = "failed"

    try:
        run_id = record_prompt_run(
            settings,
            prompt_id=payload.prompt_id,
            prompt_version=payload.prompt_version,
            model=payload.model,
            status=status,
            input_refs=payload.input_refs,
            output=payload.output,
            parse_ok=parse_ok,
            error_text=error_text,
            actor=payload.actor,
            run_id=payload.run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    item = get_prompt_run(settings, run_id)
    if item is None:
        raise HTTPException(status_code=500, detail="Run was written but could not be loaded.")
    if wants_html(request):
        return HTMLResponse(render("fragments/run_detail.html", item=item))
    return item


@router.get("/{run_id}", response_model=None)
def run_detail(request: Request, run_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = get_prompt_run(settings, run_id)
    if not item:
        raise HTTPException(status_code=404, detail="Run not found.")
    if wants_html(request):
        return HTMLResponse(render("fragments/run_detail.html", item=item))
    return item


@router.post("/{run_id}/retry", response_model=None)
async def run_retry(request: Request, run_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await read_form_body(request)
        body = {key: form_first(form, key) for key in form.keys()}
    payload = RetryRunRequest.model_validate(body or {})

    try:
        retried_run_id = retry_prompt_run(settings, source_run_id=run_id, actor=payload.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    item = get_prompt_run(settings, retried_run_id)
    if item is None:
        raise HTTPException(status_code=500, detail="Retry run was written but could not be loaded.")
    if wants_html(request):
        return HTMLResponse(render("fragments/run_detail.html", item=item))
    return item
