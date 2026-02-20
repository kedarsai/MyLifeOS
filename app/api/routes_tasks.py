from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.projects import list_projects
from app.services.tasks import assign_task_project, delete_task, list_tasks, list_today_tasks, quick_complete_task
from app.ui.templating import render, wants_html


tasks_router = APIRouter(prefix="/api/tasks", tags=["tasks"])
today_router = APIRouter(prefix="/api/today", tags=["today"])


class AssignProjectRequest(BaseModel):
    project_id: str | None = None


def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _filters_dict(
    *,
    status: str | None,
    goal_id: str | None,
    project_id: str | None,
    q: str | None,
    include_done: bool,
    limit: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {"limit": limit}
    if status:
        out["status"] = status
    if goal_id:
        out["goal_id"] = goal_id
    if project_id:
        out["project_id"] = project_id
    if q:
        out["q"] = q
    if include_done:
        out["include_done"] = "1"
    return out


def _render_tasks_html(
    *,
    items: list[dict[str, Any]],
    total: int,
    filters: dict[str, Any],
    notice: str | None = None,
    project_options: list[dict[str, Any]] | None = None,
) -> str:
    project_options = project_options or []
    qs = urlencode(filters)
    return render(
        "fragments/tasks_fragment.html",
        items=items,
        total=total,
        qs=qs,
        project_options=project_options,
        notice=notice,
    )


def _render_today_html(data: dict[str, Any], notice: str | None = None) -> str:
    return render(
        "fragments/today_fragment.html",
        data=data,
        notice=notice,
    )


@today_router.get("", response_model=None)
def today_view(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    data = list_today_tasks(settings)
    if wants_html(request):
        return HTMLResponse(_render_today_html(data))
    return data


@tasks_router.get("", response_model=None)
def tasks_list(
    request: Request,
    status: str | None = Query(default=None),
    goal_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_done: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    result = list_tasks(
        settings,
        status=status,
        goal_id=goal_id,
        project_id=project_id,
        q=q,
        include_done=include_done,
        limit=limit,
    )
    payload = {
        "items": result["items"],
        "total": result["total"],
        "filters": _filters_dict(
            status=status,
            goal_id=goal_id,
            project_id=project_id,
            q=q,
            include_done=include_done,
            limit=limit,
        ),
    }
    if wants_html(request):
        return HTMLResponse(_render_tasks_html(
            items=result["items"],
            total=result["total"],
            filters=payload["filters"],
            project_options=list_projects(settings),
        ))
    return payload


@tasks_router.post("/{task_id}/complete", response_model=None)
def task_complete(
    request: Request,
    task_id: str,
    view: str | None = Query(default=None),
    status: str | None = Query(default=None),
    goal_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_done: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    ok = quick_complete_task(settings, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found.")

    if view == "tasks":
        parsed_include_done = _truthy(include_done)
        result = list_tasks(
            settings,
            status=status,
            goal_id=goal_id,
            project_id=project_id,
            q=q,
            include_done=parsed_include_done,
            limit=limit,
        )
        filters = _filters_dict(
            status=status,
            goal_id=goal_id,
            project_id=project_id,
            q=q,
            include_done=parsed_include_done,
            limit=limit,
        )
        if wants_html(request):
            return HTMLResponse(_render_tasks_html(
                items=result["items"],
                total=result["total"],
                filters=filters,
                notice="Task completed.",
                project_options=list_projects(settings),
            ))
        return {"ok": True, "filters": filters}

    data = list_today_tasks(settings)
    if wants_html(request):
        return HTMLResponse(_render_today_html(data, notice="Task completed."))
    return {"ok": True}


@tasks_router.post("/{task_id}/delete", response_model=None)
def task_delete(
    request: Request,
    task_id: str,
    view: str | None = Query(default=None),
    status: str | None = Query(default=None),
    goal_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_done: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    ok = delete_task(settings, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found.")

    if view == "tasks":
        parsed_include_done = _truthy(include_done)
        result = list_tasks(
            settings,
            status=status,
            goal_id=goal_id,
            project_id=project_id,
            q=q,
            include_done=parsed_include_done,
            limit=limit,
        )
        filters = _filters_dict(
            status=status,
            goal_id=goal_id,
            project_id=project_id,
            q=q,
            include_done=parsed_include_done,
            limit=limit,
        )
        if wants_html(request):
            return HTMLResponse(_render_tasks_html(
                items=result["items"],
                total=result["total"],
                filters=filters,
                notice="Task deleted.",
                project_options=list_projects(settings),
            ))
        return {"ok": True, "filters": filters}

    data = list_today_tasks(settings)
    if wants_html(request):
        return HTMLResponse(_render_today_html(data, notice="Task deleted."))
    return {"ok": True}


@tasks_router.post("/{task_id}/project", response_model=None)
async def task_assign_project(
    request: Request,
    task_id: str,
    view: str | None = Query(default=None),
    status: str | None = Query(default=None),
    goal_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_done: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> Any:
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
        payload = AssignProjectRequest.model_validate(body or {})
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    ok = assign_task_project(settings, task_id=task_id, project_id=payload.project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task or project not found.")

    parsed_include_done = _truthy(include_done)
    result = list_tasks(
        settings,
        status=status,
        goal_id=goal_id,
        project_id=project_id,
        q=q,
        include_done=parsed_include_done,
        limit=limit,
    )
    filters = _filters_dict(
        status=status,
        goal_id=goal_id,
        project_id=project_id,
        q=q,
        include_done=parsed_include_done,
        limit=limit,
    )
    if view == "tasks" and wants_html(request):
        return HTMLResponse(_render_tasks_html(
            items=result["items"],
            total=result["total"],
            filters=filters,
            notice="Project assignment updated.",
            project_options=list_projects(settings),
        ))
    return {"ok": True}
