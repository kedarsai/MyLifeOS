from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.migrations import apply_sql_migrations
from app.services.topics import (
    attention_heatmap,
    get_topic_detail,
    list_areas,
    list_topics,
)

router = APIRouter(prefix="/api/thoughts", tags=["thoughts"])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@router.get("/areas", response_model=None)
def areas_list(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_areas(settings)
    return {"items": items, "total": len(items)}


@router.get("/areas/{area_id}/topics", response_model=None)
def area_topics(request: Request, area_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_topics(settings, area_id=area_id)
    return {"items": items, "total": len(items)}


@router.get("/topics/{topic_id}", response_model=None)
def topic_detail(request: Request, topic_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = get_topic_detail(settings, topic_id)
    if not item:
        raise HTTPException(status_code=404, detail="Topic not found.")
    return item


@router.get("/heatmap", response_model=None)
def heatmap(request: Request, months: int = Query(default=6, ge=1, le=24)) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    cells = attention_heatmap(settings, months=months)
    return {"items": cells}
