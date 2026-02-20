from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.services.search import search_entries
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/search", tags=["search"])

ENTRY_TYPES = {
    "activity",
    "sleep",
    "food",
    "thought",
    "idea",
    "todo",
    "goal",
    "note",
    "chat",
}


def _query_url(
    *,
    q: str,
    page: int,
    page_size: int,
    entry_type: str | None,
    tag: str | None,
    goal: str | None,
) -> str:
    params: dict[str, Any] = {
        "format": "html",
        "q": q,
        "page": page,
        "page_size": page_size,
    }
    if entry_type:
        params["type"] = entry_type
    if tag:
        params["tag"] = tag
    if goal:
        params["goal"] = goal
    return f"/api/search?{urlencode(params)}"


@router.get("", response_model=None)
def search(
    request: Request,
    q: str = Query(min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    type: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    goal: str | None = Query(default=None),
) -> Any:
    entry_type = type.strip().lower() if type else None
    if entry_type and entry_type not in ENTRY_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported entry type: {type}")
    try:
        result = search_entries(
            request.app.state.settings,
            q=q,
            entry_type=entry_type,
            tag=(tag.strip() if tag else None),
            goal=(goal.strip() if goal else None),
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload = {
        "items": result.items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
        "facets": result.facets,
    }
    if wants_html(request):
        return HTMLResponse(render(
            "fragments/search_results.html",
            q=q,
            page=result.page,
            page_size=result.page_size,
            total=result.total,
            total_pages=result.total_pages,
            entry_type=entry_type,
            tag=(tag.strip() if tag else None),
            goal=(goal.strip() if goal else None),
            items=result.items,
            facets=result.facets,
            query_url=_query_url,
        ))
    return payload
