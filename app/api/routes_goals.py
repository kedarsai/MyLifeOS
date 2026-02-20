from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.goals import create_goal, get_goal, goal_dashboard, link_entry_to_goal, list_goals, update_goal
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    start_date: str = Field(min_length=8, max_length=20)
    end_date: str | None = None
    rules_md: str = ""
    metrics: list[str] = Field(default_factory=list)
    status: str = Field(default="active")
    review_cadence_days: int = Field(default=7, ge=1, le=365)


class GoalUpdateRequest(BaseModel):
    name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    rules_md: str | None = None
    metrics: list[str] | None = None
    status: str | None = None
    review_cadence_days: int | None = Field(default=None, ge=1, le=365)


class GoalLinkRequest(BaseModel):
    entry_id: str = Field(min_length=1)
    link_type: str = Field(default="related")


def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def _parse_metrics(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


@router.get("", response_model=None)
def goals_list(request: Request, status: str | None = Query(default=None)) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_goals(settings, status=status)
    if wants_html(request):
        return HTMLResponse(render("fragments/goals_list.html", items=items))
    return {"items": items, "total": len(items)}


@router.post("", response_model=None)
async def goals_create(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await read_form_body(request)
        body = {
            "name": form_first(form, "name"),
            "start_date": form_first(form, "start_date"),
            "end_date": form_first(form, "end_date") or None,
            "rules_md": form_first(form, "rules_md") or "",
            "metrics": _parse_metrics(form_first(form, "metrics")),
            "status": form_first(form, "status") or "active",
            "review_cadence_days": int(str(form_first(form, "review_cadence_days") or "7")),
        }
    payload = GoalCreateRequest.model_validate(body)
    item = create_goal(
        settings,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        rules_md=payload.rules_md,
        metrics=payload.metrics,
        status=payload.status,
        review_cadence_days=payload.review_cadence_days,
    )
    if wants_html(request):
        items = list_goals(settings, status=None)
        return HTMLResponse(render("fragments/goals_list.html", items=items, notice=f"Created goal {item['name']}"))
    return item


@router.get("/{goal_id}", response_model=None)
def goals_get(request: Request, goal_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = get_goal(settings, goal_id)
    if not item:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return item


@router.patch("/{goal_id}", response_model=None)
def goals_patch(request: Request, goal_id: str, payload: GoalUpdateRequest) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = update_goal(settings, goal_id, payload.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return item


@router.post("/{goal_id}/link-entry", response_model=None)
def goals_link_entry(request: Request, goal_id: str, payload: GoalLinkRequest) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    ok = link_entry_to_goal(settings, goal_id=goal_id, entry_id=payload.entry_id, link_type=payload.link_type)
    if not ok:
        raise HTTPException(status_code=404, detail="Goal or entry not found.")
    return {"ok": True}


@router.get("/{goal_id}/dashboard", response_model=None)
def goals_dashboard(request: Request, goal_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = goal_dashboard(settings, goal_id=goal_id)
    if not item:
        raise HTTPException(status_code=404, detail="Goal not found.")
    if wants_html(request):
        return HTMLResponse(render("fragments/goal_dashboard.html", item=item))
    return item
