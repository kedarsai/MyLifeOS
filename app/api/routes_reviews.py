from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.reviews import generate_weekly_review, list_weekly_reviews
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class GenerateReviewRequest(BaseModel):
    goal_id: str = Field(min_length=1)
    week_start: str | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def _read_generate_payload(request: Request) -> GenerateReviewRequest:
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
        return GenerateReviewRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.get("", response_model=None)
def reviews_list(request: Request, goal_id: str | None = Query(default=None)) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_weekly_reviews(settings, goal_id=goal_id)
    if wants_html(request):
        return HTMLResponse(render("fragments/reviews_list.html", items=items))
    return {"items": items, "total": len(items)}


@router.post("/generate", response_model=None)
async def reviews_generate(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = await _read_generate_payload(request)
    try:
        item = generate_weekly_review(settings, goal_id=payload.goal_id, week_start=payload.week_start)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if wants_html(request):
        items = list_weekly_reviews(settings, goal_id=payload.goal_id)
        return HTMLResponse(render("fragments/reviews_list.html", items=items, notice=f"Generated weekly review for {payload.goal_id}."))
    return item
