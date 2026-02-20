from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db.migrations import apply_sql_migrations
from app.services.goals import list_goals
from app.services.projects import list_projects as list_projects_service
from app.ui.templating import CAPTURE_FLOW, GOAL_FLOW, render_page


router = APIRouter(tags=["ui"])

ENTRY_TYPES = [
    "activity",
    "sleep",
    "food",
    "thought",
    "idea",
    "todo",
    "goal",
    "note",
    "chat",
]


def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


@router.get("/")
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> str:
    return HTMLResponse(render_page("pages/dashboard.html", request=None,
        title="LifeOS Dashboard", active="/dashboard", layout="default"))


@router.get("/capture", response_class=HTMLResponse)
def capture_page() -> str:
    return HTMLResponse(render_page("pages/capture.html", request=None,
        title="LifeOS Capture", active="/capture", layout="focused",
        entry_types=ENTRY_TYPES,
        steps=CAPTURE_FLOW, current="/capture"))


@router.get("/goals", response_class=HTMLResponse)
def goals_page() -> str:
    return HTMLResponse(render_page("pages/goals.html", request=None,
        title="LifeOS Goals", active="/goals", layout="default",
        steps=GOAL_FLOW, current="/goals"))


@router.get("/projects", response_class=HTMLResponse)
def projects_page() -> str:
    return HTMLResponse(render_page("pages/projects.html", request=None,
        title="LifeOS Projects", active="/projects", layout="default"))


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    status: str | None = None,
    goal_id: str | None = None,
    project_id: str | None = None,
    q: str | None = None,
    include_done: bool = False,
    limit: int = 200,
) -> str:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    goals = list_goals(settings)
    projects = list_projects_service(settings)

    today_label = date.today().isoformat()
    initial_qs = urlencode(
        {
            "format": "html",
            "status": status or "",
            "goal_id": goal_id or "",
            "project_id": project_id or "",
            "q": q or "",
            "include_done": "1" if include_done else "0",
            "limit": int(limit),
        }
    )
    return HTMLResponse(render_page("pages/tasks.html", request,
        title="LifeOS Tasks", active="/tasks", layout="wide",
        steps=GOAL_FLOW, current="/tasks",
        goals=goals, projects=projects,
        status=status, goal_id=goal_id, project_id=project_id,
        q=q, include_done=include_done, limit=limit,
        today_label=today_label, initial_qs=initial_qs))


@router.get("/today", response_class=HTMLResponse)
def today_page() -> str:
    return HTMLResponse(render_page("pages/today.html", request=None,
        title="LifeOS Today", active="/today", layout="default"))


@router.get("/improvements", response_class=HTMLResponse)
def improvements_page(request: Request) -> str:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    goals = list_goals(settings)

    return HTMLResponse(render_page("pages/improvements.html", request,
        title="LifeOS Improvements", active="/improvements", layout="default",
        steps=GOAL_FLOW, current="/improvements",
        goals=goals))


@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request) -> str:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    goals = list_goals(settings)

    return HTMLResponse(render_page("pages/chat.html", request,
        title="LifeOS Goal Chat", active="/chat", layout="split",
        steps=GOAL_FLOW, current="/chat",
        goals=goals))


@router.get("/reminders", response_class=HTMLResponse)
def reminders_page(request: Request) -> str:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    goals = list_goals(settings)

    return HTMLResponse(render_page("pages/reminders.html", request,
        title="LifeOS Reminders", active="/reminders", layout="default",
        goals=goals))


@router.get("/reviews", response_class=HTMLResponse)
def reviews_page(request: Request) -> str:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    goals = list_goals(settings)

    return HTMLResponse(render_page("pages/reviews.html", request,
        title="LifeOS Reviews", active="/reviews", layout="default",
        steps=GOAL_FLOW, current="/reviews",
        goals=goals))


@router.get("/inbox", response_class=HTMLResponse)
def inbox_page() -> str:
    return HTMLResponse(render_page("pages/inbox.html", request=None,
        title="LifeOS Inbox", active="/inbox", layout="default",
        steps=CAPTURE_FLOW, current="/inbox"))


@router.get("/timeline", response_class=HTMLResponse)
def timeline_page(request: Request) -> str:
    settings = request.app.state.settings
    apply_sql_migrations(_project_root(), settings)
    goals = list_goals(settings)

    return HTMLResponse(render_page("pages/timeline.html", request,
        title="LifeOS Timeline", active="/timeline", layout="wide",
        steps=CAPTURE_FLOW, current="/timeline",
        entry_types=ENTRY_TYPES, goals=goals))


@router.get("/conflicts", response_class=HTMLResponse)
def conflicts_page() -> str:
    return HTMLResponse(render_page("pages/conflicts.html", request=None,
        title="LifeOS Conflict Center", active="/conflicts", layout="split"))


@router.get("/search", response_class=HTMLResponse)
def search_page() -> str:
    return HTMLResponse(render_page("pages/search.html", request=None,
        title="LifeOS Search", active="/search", layout="default",
        entry_types=ENTRY_TYPES))


@router.get("/prompts", response_class=HTMLResponse)
def prompts_page() -> str:
    return HTMLResponse(render_page("pages/prompts.html", request=None,
        title="LifeOS Prompt Registry", active="/prompts", layout="default"))


@router.get("/runs", response_class=HTMLResponse)
def runs_page() -> str:
    return HTMLResponse(render_page("pages/runs.html", request=None,
        title="LifeOS Prompt Runs", active="/runs", layout="split"))
