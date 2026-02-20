from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.form_utils import form_first, read_form_body
from app.services.conflicts import count_open_conflicts, get_conflict, list_conflicts, resolve_conflict
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/conflicts", tags=["conflicts"])


class ResolveConflictRequest(BaseModel):
    action: str = Field(pattern="^(keep_vault|keep_app|merge)$")
    actor: str = Field(default="local_user", min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)


@router.get("/badge", response_model=None)
def conflict_badge(request: Request) -> Any:
    count = count_open_conflicts(request.app.state.settings)
    if wants_html(request):
        return HTMLResponse(render("fragments/conflict_badge.html", count=count))
    return {"open_count": count}


@router.get("", response_model=None)
def conflicts_list(
    request: Request,
    status: str = Query(default="open"),
    entity_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Any:
    try:
        result = list_conflicts(
            request.app.state.settings,
            status=status,
            entity_type=entity_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload = {
        "items": result.items,
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
    }
    if wants_html(request):
        return HTMLResponse(render(
            "fragments/conflict_list.html",
            items=result.items,
            total=result.total,
            limit=result.limit,
            offset=result.offset,
        ))
    return payload


@router.get("/{conflict_id}", response_model=None)
def conflict_detail(request: Request, conflict_id: str) -> Any:
    item = get_conflict(request.app.state.settings, conflict_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conflict not found.")
    if wants_html(request):
        return HTMLResponse(render("fragments/conflict_detail.html", item=item))
    return item


@router.post("/{conflict_id}/resolve", response_model=None)
async def conflict_resolve(request: Request, conflict_id: str) -> Any:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await read_form_body(request)
        body = {key: form_first(form, key) for key in form.keys()}

    try:
        payload = ResolveConflictRequest.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid resolve payload.") from exc

    try:
        item = resolve_conflict(
            request.app.state.settings,
            conflict_id=conflict_id,
            action=payload.action,
            actor=payload.actor,
            notes=payload.notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if wants_html(request):
        return HTMLResponse(render(
            "fragments/conflict_detail.html",
            item=item,
            notice=f"Resolved with action: {payload.action}",
        ))
    return item
