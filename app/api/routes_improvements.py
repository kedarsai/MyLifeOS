from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.improvements import create_improvement, list_improvements, update_improvement_status
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/improvements", tags=["improvements"])


class ImprovementCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    rationale: str = Field(min_length=1, max_length=4000)
    source_entry_id: str | None = None
    source_run_id: str = Field(min_length=1)
    goal_id: str | None = None
    status: str = Field(default="open")


class ImprovementStatusRequest(BaseModel):
    status: str = Field(pattern="^(open|in_progress|adopted|dismissed)$")


def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


@router.get("", response_model=None)
def improvements_list(
    request: Request,
    status: str | None = Query(default=None),
    goal_id: str | None = Query(default=None),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_improvements(settings, status=status, goal_id=goal_id)
    if wants_html(request):
        return HTMLResponse(render("fragments/improvements_list.html", items=items))
    return {"items": items, "total": len(items)}


@router.post("", response_model=None)
async def improvements_create(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await read_form_body(request)
        body = {key: form_first(form, key) for key in form.keys()}
    payload = ImprovementCreateRequest.model_validate(body)
    item = create_improvement(
        settings,
        title=payload.title,
        rationale=payload.rationale,
        source_entry_id=payload.source_entry_id,
        source_run_id=payload.source_run_id,
        goal_id=payload.goal_id,
        status=payload.status,
    )
    if wants_html(request):
        items = list_improvements(settings)
        return HTMLResponse(render("fragments/improvements_list.html", items=items, notice=f"Created improvement: {item['title']}"))
    return item


@router.patch("/{improvement_id}/status", response_model=None)
async def improvements_status(request: Request, improvement_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await read_form_body(request)
        body = {key: form_first(form, key) for key in form.keys()}
    payload = ImprovementStatusRequest.model_validate(body)
    ok = update_improvement_status(settings, improvement_id, payload.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Improvement not found.")
    items = list_improvements(settings)
    if wants_html(request):
        return HTMLResponse(render("fragments/improvements_list.html", items=items, notice="Updated improvement status."))
    return {"ok": True}
