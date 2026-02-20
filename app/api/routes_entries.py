from pathlib import Path
from urllib.parse import urlencode
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.form_utils import form_first, form_list, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.capture_batch import parse_batch_capture_text
from app.services.capture import capture_entry
from app.services.entries import get_entry, process_inbox_entries, query_entries
from app.services.indexer import VaultIndexer
from app.vault.manager import VaultManager
from app.ui.templating import render, wants_html

router = APIRouter(prefix="/api/entries", tags=["entries"])

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


class CaptureRequest(BaseModel):
    raw_text: str = Field(min_length=1)
    type: str = Field(default="note")
    tags: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)


class ProcessInboxRequest(BaseModel):
    entry_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=200)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _split_csv(raw_value: object) -> list[str]:
    if raw_value is None:
        return []
    value = str(raw_value).strip()
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _normalize_capture_payload(data: dict) -> CaptureRequest:
    payload = CaptureRequest.model_validate(data)
    entry_type = payload.type.strip().lower()
    if entry_type not in ENTRY_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported entry type: {payload.type}")
    return CaptureRequest(
        raw_text=payload.raw_text,
        type=entry_type,
        tags=[tag.strip() for tag in payload.tags if tag.strip()],
        goals=[goal.strip() for goal in payload.goals if goal.strip()],
    )


async def _read_capture_payload(request: Request) -> CaptureRequest:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="JSON body must be an object.")
        try:
            return _normalize_capture_payload(data)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc

    form = await read_form_body(request)
    data = {
        "raw_text": str(form_first(form, "raw_text") or ""),
        "type": str(form_first(form, "type") or "note"),
        "tags": _split_csv(form_first(form, "tags")),
        "goals": _split_csv(form_first(form, "goals")),
    }
    try:
        return _normalize_capture_payload(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


async def _read_process_payload(request: Request) -> ProcessInboxRequest:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="JSON body must be an object.")
        try:
            return ProcessInboxRequest.model_validate(data)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc

    form = await read_form_body(request)
    limit_raw = str(form_first(form, "limit") or "50").strip()
    try:
        limit = int(limit_raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="limit must be an integer.")
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200.")

    return ProcessInboxRequest(
        entry_ids=[str(v) for v in form_list(form, "entry_ids") if str(v).strip()],
        limit=limit,
    )


@router.post("/capture", response_model=None)
async def capture(request: Request) -> Any:
    payload = await _read_capture_payload(request)
    settings = request.app.state.settings
    VaultManager(settings).ensure_layout()
    apply_sql_migrations(_project_root(), settings)

    result = capture_entry(
        settings=settings,
        raw_text=payload.raw_text,
        entry_type=payload.type,
        tags=payload.tags,
        goals=payload.goals,
    )
    VaultIndexer(settings).index_paths([result.path])
    response = {
        "entry_id": result.entry_id,
        "source_run_id": result.source_run_id,
        "path": str(result.path),
        "created": result.created,
    }
    if wants_html(request):
        inbox_result = query_entries(settings, status="inbox", limit=1, offset=0)
        return HTMLResponse(render(
            "fragments/capture_result.html",
            item=response,
            inbox_count=inbox_result.total,
        ))
    return response


@router.post("/capture/batch", response_model=None)
async def capture_batch(request: Request) -> Any:
    payload = await _read_capture_payload(request)
    items = parse_batch_capture_text(payload.raw_text)
    if not items:
        raise HTTPException(status_code=422, detail="No batch items detected.")

    settings = request.app.state.settings
    VaultManager(settings).ensure_layout()
    apply_sql_migrations(_project_root(), settings)

    results = []
    paths = []
    for raw_item in items:
        captured = capture_entry(
            settings=settings,
            raw_text=raw_item,
            entry_type=payload.type,
            tags=payload.tags,
            goals=payload.goals,
        )
        paths.append(captured.path)
        results.append(
            {
                "entry_id": captured.entry_id,
                "source_run_id": captured.source_run_id,
                "path": str(captured.path),
                "created": captured.created,
            }
        )
    VaultIndexer(settings).index_paths(paths)

    response = {"count": len(results), "items": results}
    if wants_html(request):
        inbox_result = query_entries(settings, status="inbox", limit=1, offset=0)
        return HTMLResponse(render(
            "fragments/batch_capture_result.html",
            items=results,
            inbox_count=inbox_result.total,
        ))
    return response


@router.get("/inbox", response_model=None)
def list_inbox(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)

    result = query_entries(
        settings,
        status="inbox",
        limit=limit,
        offset=offset,
    )
    response = {
        "items": result.items,
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
    }
    if wants_html(request):
        return HTMLResponse(render(
            "fragments/inbox_list.html",
            items=result.items,
            total=result.total,
            limit=result.limit,
            offset=result.offset,
        ))
    return response


@router.post("/process-inbox", response_model=None)
async def process_inbox(request: Request) -> Any:
    payload = await _read_process_payload(request)
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)

    process_result = process_inbox_entries(
        settings,
        entry_ids=payload.entry_ids,
        limit=payload.limit,
    )
    response = {
        "selected_count": process_result.selected_count,
        "processed_count": len(process_result.processed_ids),
        "processed_ids": process_result.processed_ids,
        "failed_count": len(process_result.failed_ids),
        "failed_ids": process_result.failed_ids,
        "missing_paths": process_result.missing_paths,
        "run_ids": process_result.run_ids,
        "observations_indexed": process_result.observations_indexed,
        "tasks_synced": process_result.tasks_synced,
        "improvements_created": process_result.improvements_created,
    }
    if wants_html(request):
        refreshed = query_entries(settings, status="inbox", limit=payload.limit, offset=0)
        notice = (
            f"Processed {len(process_result.processed_ids)} entries."
            if process_result.processed_ids
            else "No inbox entries were processed."
        )
        if process_result.failed_ids:
            notice += f" Failed schema checks: {len(process_result.failed_ids)}."
        if process_result.missing_paths:
            notice += f" Missing files: {len(process_result.missing_paths)}."
        if process_result.run_ids:
            notice += f" Logged runs: {len(process_result.run_ids)} (see /runs)."
        if process_result.observations_indexed:
            notice += f" Activity observations: {process_result.observations_indexed}."
        if process_result.tasks_synced:
            notice += f" Tasks synced: {process_result.tasks_synced}."
        if process_result.improvements_created:
            notice += f" Improvements: {process_result.improvements_created}."
        return HTMLResponse(render(
            "fragments/inbox_list.html",
            items=refreshed.items,
            total=refreshed.total,
            limit=refreshed.limit,
            offset=refreshed.offset,
            notice=notice,
        ))
    return response


@router.get("/timeline", response_model=None)
def list_timeline(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    type: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    goal: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)

    entry_type = type.strip().lower() if type else None
    if entry_type and entry_type not in ENTRY_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported entry type: {type}")

    offset = (page - 1) * page_size
    result = query_entries(
        settings,
        entry_type=entry_type,
        tag=(tag.strip() if tag else None),
        goal=(goal.strip() if goal else None),
        date_from=(date_from.strip() if date_from else None),
        date_to=(date_to.strip() if date_to else None),
        limit=page_size,
        offset=offset,
    )
    total_pages = max(1, (result.total + page_size - 1) // page_size)
    response = {
        "items": result.items,
        "total": result.total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
    if wants_html(request):
        base_params: dict[str, Any] = {"format": "html", "page_size": page_size}
        if entry_type:
            base_params["type"] = entry_type
        if tag:
            base_params["tag"] = tag.strip()
        if goal:
            base_params["goal"] = goal.strip()
        if date_from:
            base_params["date_from"] = date_from.strip()
        if date_to:
            base_params["date_to"] = date_to.strip()
        pager_base = urlencode(base_params)
        return HTMLResponse(render(
            "fragments/timeline_list.html",
            items=result.items,
            total=result.total,
            page=page,
            page_size=page_size,
            pager_base=pager_base,
        ))
    return response


@router.get("/{entry_id}", response_model=None)
def entry_detail(request: Request, entry_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = get_entry(settings, entry_id)
    if not item:
        raise HTTPException(status_code=404, detail="Entry not found.")
    return item
