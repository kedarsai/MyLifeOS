from __future__ import annotations

from html import escape
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.form_utils import form_first, read_form_body
from app.db.migrations import apply_sql_migrations
from app.services.chats import (
    add_chat_message,
    build_chat_context,
    build_entity_chat_context,
    create_chat_thread,
    distill_chat_outcomes,
    execute_proposed_action,
    generate_thread_reply,
    get_chat_thread,
    list_chat_messages,
    list_chat_threads,
)
from app.ui.templating import render, wants_html


router = APIRouter(prefix="/api/chat", tags=["chat"])


class CreateThreadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    goal_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None


class AddMessageRequest(BaseModel):
    role: str = Field(pattern="^(system|user|assistant|tool)$")
    content: str = Field(min_length=1, max_length=20000)


def _project_root():
    from pathlib import Path

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


@router.get("/threads", response_model=None)
def threads_list(
    request: Request,
    goal_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    items = list_chat_threads(settings, goal_id=goal_id, entity_type=entity_type, entity_id=entity_id)
    if wants_html(request):
        return HTMLResponse(render("fragments/chat_threads.html", items=items))
    return {"items": items, "total": len(items)}


@router.post("/threads", response_model=None)
async def threads_create(request: Request) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = CreateThreadRequest.model_validate((await _read_model_payload(request, CreateThreadRequest)).model_dump())
    item = create_chat_thread(
        settings,
        title=payload.title,
        goal_id=payload.goal_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
    )
    if wants_html(request):
        items = list_chat_threads(settings, goal_id=None)
        return HTMLResponse(render("fragments/chat_threads.html", items=items, notice=f"Created thread: {item['title']}"))
    return item


@router.get("/threads/{thread_id}", response_model=None)
def thread_get(request: Request, thread_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    item = get_chat_thread(settings, thread_id)
    if not item:
        raise HTTPException(status_code=404, detail="Thread not found.")
    return item


@router.get("/threads/{thread_id}/messages", response_model=None)
def messages_list(request: Request, thread_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    thread = get_chat_thread(settings, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    messages = list_chat_messages(settings, thread_id=thread_id)
    if wants_html(request):
        return HTMLResponse(render("fragments/chat_messages.html", messages=messages))
    return {"items": messages, "total": len(messages)}


@router.post("/threads/{thread_id}/messages", response_model=None)
async def messages_add(request: Request, thread_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = AddMessageRequest.model_validate((await _read_model_payload(request, AddMessageRequest)).model_dump())
    try:
        item = add_chat_message(settings, thread_id=thread_id, role=payload.role, content=payload.content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if wants_html(request):
        messages = list_chat_messages(settings, thread_id=thread_id)
        return HTMLResponse(render("fragments/chat_messages.html", messages=messages))
    return item


@router.get("/context", response_model=None)
def chat_context(
    request: Request,
    goal_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    if entity_type and entity_id:
        return build_entity_chat_context(settings, entity_type=entity_type, entity_id=entity_id)
    return build_chat_context(settings, goal_id=goal_id)


@router.post("/threads/{thread_id}/distill", response_model=None)
def distill_thread(request: Request, thread_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    try:
        item = distill_chat_outcomes(settings, thread_id=thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if wants_html(request):
        return HTMLResponse(
            "<div class='result success'>"
            f"Distilled thread {escape(thread_id)}. "
            f"Insight: {escape(item['insight_id'])}, Improvement: {escape(item['improvement_id'])}, "
            f"Tasks: {item['tasks_created_or_updated']}."
            "</div>"
        )
    return item


@router.post("/threads/{thread_id}/reply", response_model=None)
def thread_reply(request: Request, thread_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    try:
        item = generate_thread_reply(settings, thread_id=thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if wants_html(request):
        messages = list_chat_messages(settings, thread_id=thread_id)
        return HTMLResponse(render("fragments/chat_messages.html", messages=messages))
    return item


class ConfirmActionRequest(BaseModel):
    action_type: str
    label: str = ""
    params: dict = {}


@router.post("/threads/{thread_id}/confirm-action", response_model=None)
async def confirm_action(request: Request, thread_id: str) -> Any:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    payload = await _read_model_payload(request, ConfirmActionRequest)
    try:
        result = execute_proposed_action(
            settings,
            thread_id=thread_id,
            action=payload.model_dump(),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result
