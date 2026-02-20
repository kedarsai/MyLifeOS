from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.ideas import (
    convert_idea,
    create_idea,
    get_idea_detail,
    list_ideas,
    update_entry_link_note,
    update_idea,
)

router = APIRouter(prefix="/api/ideas", tags=["ideas"])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class CreateIdeaRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    status: str = "raw"


class UpdateIdeaRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class UpdateEntryNoteRequest(BaseModel):
    note: str = ""


class ConvertIdeaRequest(BaseModel):
    target_type: str = Field(pattern="^(goal|project|task)$")
    name: str | None = None
    kind: str | None = None
    start_date: str | None = None


async def _read_model_payload(request: Request, model_cls: type[BaseModel]) -> BaseModel:
    from pydantic import ValidationError
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
        return model_cls.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.get("", response_model=None)
def ideas_list(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_ideas(settings, status=status, limit=limit)
    return {"items": items, "total": len(items)}


@router.post("", response_model=None)
async def ideas_create(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = await _read_model_payload(request, CreateIdeaRequest)
    import uuid
    run_id = f"manual-{uuid.uuid4()}"
    from app.services.ideas import _ensure_run_global
    _ensure_run_global(settings, run_id)
    item = create_idea(
        settings,
        title=payload.title,
        description=payload.description,
        source_run_id=run_id,
        status=payload.status,
    )
    return item


@router.get("/{idea_id}", response_model=None)
def idea_detail(request: Request, idea_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = get_idea_detail(settings, idea_id)
    if not item:
        raise HTTPException(status_code=404, detail="Idea not found.")
    return item


@router.patch("/{idea_id}", response_model=None)
async def idea_update(request: Request, idea_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = await _read_model_payload(request, UpdateIdeaRequest)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    item = update_idea(settings, idea_id, updates)
    if not item:
        raise HTTPException(status_code=404, detail="Idea not found or not current.")
    return item


@router.post("/{idea_id}/convert", response_model=None)
async def idea_convert(request: Request, idea_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = await _read_model_payload(request, ConvertIdeaRequest)
    try:
        result = convert_idea(
            settings,
            idea_id,
            target_type=payload.target_type,
            extra=payload.model_dump(exclude_none=True),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.patch("/{idea_id}/entries/{entry_id}", response_model=None)
async def idea_entry_note_update(
    request: Request, idea_id: str, entry_id: str,
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = await _read_model_payload(request, UpdateEntryNoteRequest)
    updated = update_entry_link_note(
        settings, idea_id=idea_id, entry_id=entry_id, note=payload.note,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Idea-entry link not found.")
    return {"ok": True, "idea_id": idea_id, "entry_id": entry_id, "note": payload.note}
