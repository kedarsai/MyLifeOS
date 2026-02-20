from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.capture import capture_entry
from app.services.entries import process_inbox_entries
from app.services.indexer import VaultIndexer
from app.services.reminders import backup_status, reminders_summary
from app.tools.backup_local import run as run_backup
from app.vault.manager import VaultManager
from app.ui.templating import render, wants_html


router = APIRouter(tags=["reminders"])


class CheckinRequest(BaseModel):
    date: str | None = None
    notes: str = Field(default="", max_length=8000)
    goal_id: str | None = None


class BackupRequest(BaseModel):
    mode: str = Field(pattern="^(hourly|daily)$")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def _read_model_payload(request: Request, model_cls: type[BaseModel]) -> BaseModel:
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


def _checkin_created_iso(settings, day_text: str | None) -> str | None:
    if not day_text:
        return None
    try:
        parsed_day = date.fromisoformat(day_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD.") from exc
    try:
        tz = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    return datetime.combine(parsed_day, time(hour=12, minute=0, second=0), tzinfo=tz).isoformat()


@router.get("/api/reminders", response_model=None)
def reminders(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    data = reminders_summary(settings)
    if wants_html(request):
        return HTMLResponse(render("fragments/reminders_summary.html", data=data))
    return data


def _checkin_entry_type(kind: str) -> str:
    mapping = {"sleep": "sleep", "food": "food", "activity": "activity"}
    if kind not in mapping:
        raise KeyError("Unsupported check-in kind.")
    return mapping[kind]


@router.post("/api/checkin/{kind}", response_model=None)
async def checkin(request: Request, kind: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = CheckinRequest.model_validate((await _read_model_payload(request, CheckinRequest)).model_dump())
    try:
        entry_type = _checkin_entry_type(kind)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    manager = VaultManager(settings)
    manager.ensure_layout()
    date_prefix = f"Date: {payload.date}\n" if payload.date else ""
    raw = f"{date_prefix}{kind.capitalize()} check-in.\n{payload.notes.strip()}".strip()
    goal_ids = [payload.goal_id] if payload.goal_id else []
    captured = capture_entry(
        settings=settings,
        raw_text=raw,
        entry_type=entry_type,
        tags=[f"checkin-{kind}"],
        goals=goal_ids,
        created_override=_checkin_created_iso(settings, payload.date),
    )
    VaultIndexer(settings).index_paths([captured.path])
    processed = process_inbox_entries(settings, entry_ids=[captured.entry_id], limit=1)
    response = {
        "entry_id": captured.entry_id,
        "path": str(captured.path),
        "type": entry_type,
        "processed_count": len(processed.processed_ids),
        "run_ids": processed.run_ids,
    }
    if wants_html(request):
        reminders_data = reminders_summary(settings)
        return HTMLResponse(render("fragments/reminders_summary.html", data=reminders_data, notice=f"Saved {kind} check-in."))
    return response


@router.get("/api/backups/status", response_model=None)
def backups_status(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return backup_status(settings)


@router.post("/api/backups/run", response_model=None)
async def backups_run(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    payload = BackupRequest.model_validate((await _read_model_payload(request, BackupRequest)).model_dump())
    out = run_backup(payload.mode, settings.vault_path, settings.db_path, Path("backups"))
    return {"ok": True, "path": str(out), "mode": payload.mode}
