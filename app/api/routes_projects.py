from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.projects import create_project, list_projects, update_project
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    kind: str = Field(default="personal", pattern="^(client|personal|internal|other)$")
    status: str = Field(default="active", pattern="^(active|paused|completed|archived)$")
    notes: str = Field(default="", max_length=4000)


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    kind: str | None = Field(default=None, pattern="^(client|personal|internal|other)$")
    status: str | None = Field(default=None, pattern="^(active|paused|completed|archived)$")
    notes: str | None = Field(default=None, max_length=4000)


def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


@router.get("", response_model=None)
def projects_list(
    request: Request,
    status: str | None = Query(default=None),
    kind: str | None = Query(default=None),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_projects(settings, status=status, kind=kind)
    if wants_html(request):
        return HTMLResponse(render("fragments/projects_list.html", items=items))
    return {"items": items, "total": len(items)}


@router.post("", response_model=None)
async def projects_create(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
    else:
        form = await read_form_body(request)
        body = {key: form_first(form, key) for key in form.keys()}
    try:
        payload = ProjectCreateRequest.model_validate(body or {})
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    item = create_project(
        settings,
        name=payload.name,
        kind=payload.kind,
        status=payload.status,
        notes=payload.notes,
    )
    if wants_html(request):
        return HTMLResponse(render("fragments/projects_list.html", items=list_projects(settings), notice=f"Created project: {item['name']}"))
    return item


@router.patch("/{project_id}", response_model=None)
async def projects_patch(request: Request, project_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
    else:
        form = await read_form_body(request)
        body = {key: form_first(form, key) for key in form.keys()}
    try:
        payload = ProjectUpdateRequest.model_validate(body or {})
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    item = update_project(settings, project_id, payload.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(status_code=404, detail="Project not found.")
    return item
