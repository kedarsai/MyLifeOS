from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.migrations import apply_sql_migrations
from app.services.cards import get_card, list_cards

router = APIRouter(prefix="/api/cards", tags=["cards"])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@router.get("", response_model=None)
def cards_list(
    request: Request,
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_cards(settings, entity_type=entity_type, entity_id=entity_id, q=q, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/{card_id}", response_model=None)
def card_detail(request: Request, card_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = get_card(settings, card_id)
    if not item:
        raise HTTPException(status_code=404, detail="Card not found.")
    return item
