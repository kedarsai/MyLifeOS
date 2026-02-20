from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

_templates_dir = Path(__file__).resolve().parent.parent / "templates"

env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=select_autoescape(["html"]),
)


# --------------- Jinja2 filters ---------------

def _time_ago(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = int((now - dt).total_seconds())
    except Exception:
        return iso[:10]
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    days = diff // 86400
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    return iso[:10]


def _truncate(text: str, max_len: int = 120) -> str:
    clean = " ".join(str(text).strip().split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1] + "\u2026"


def _snippet_to_html(snippet: str) -> str:
    """Convert [bracketed] FTS highlights to <mark> tags.  Returns Markup."""
    from markupsafe import escape as _esc
    escaped = str(_esc(snippet or ""))
    return Markup(re.sub(r"\[(.*?)\]", r"<mark>\1</mark>", escaped))


env.filters["time_ago"] = _time_ago
env.filters["truncate_text"] = _truncate
env.filters["snippet_html"] = _snippet_to_html


# --------------- shared layout constants ---------------

NAV_GROUPS = [
    (
        "Core",
        [
            ("/dashboard", "Dashboard"),
            ("/today", "Today"),
            ("/tasks", "Tasks"),
            ("/goals", "Goals"),
            ("/projects", "Projects"),
        ],
    ),
    (
        "Capture",
        [
            ("/capture", "Capture"),
            ("/inbox", "Inbox"),
            ("/timeline", "Timeline"),
        ],
    ),
    (
        "Coach",
        [
            ("/chat", "Chat"),
            ("/improvements", "Improvements"),
            ("/reviews", "Reviews"),
            ("/reminders", "Reminders"),
        ],
    ),
    (
        "System",
        [
            ("/prompts", "Prompts"),
            ("/runs", "Runs"),
            ("/conflicts", "Conflicts"),
        ],
    ),
]

PRIMARY_TABS = [
    ("/dashboard", "Dashboard"),
    ("/today", "Today"),
    ("/tasks", "Tasks"),
    ("/goals", "Goals"),
    ("/capture", "Capture"),
    ("/inbox", "Inbox"),
    ("/chat", "Chat"),
]

NAV_ICONS = {
    "/dashboard": "&#9632;",
    "/today": "&#9788;",
    "/tasks": "&#9745;",
    "/goals": "&#9733;",
    "/projects": "&#9881;",
    "/capture": "&#9998;",
    "/inbox": "&#9993;",
    "/timeline": "&#8614;",
    "/chat": "&#9993;",
    "/improvements": "&#9650;",
    "/reviews": "&#9776;",
    "/reminders": "&#9202;",
    "/prompts": "&#10070;",
    "/runs": "&#9654;",
    "/conflicts": "&#9888;",
}

CAPTURE_FLOW = [("/capture", "Capture"), ("/inbox", "Process"), ("/timeline", "View")]
GOAL_FLOW = [
    ("/goals", "Goals"),
    ("/tasks", "Tasks"),
    ("/reviews", "Reviews"),
    ("/improvements", "Improvements"),
    ("/chat", "Chat"),
]


# --------------- render helpers ---------------

def render(template_name: str, **ctx) -> str:
    return env.get_template(template_name).render(**ctx)


def render_page(template_name: str, request: Request, **ctx) -> str:
    """Render a full page template with common context."""
    title = ctx.get("title", "LifeOS")
    display_title = title.replace("LifeOS ", "") if title.startswith("LifeOS ") else title
    base_ctx = {
        "nav_groups": NAV_GROUPS,
        "primary_tabs": PRIMARY_TABS,
        "nav_icons": NAV_ICONS,
        "display_title": display_title,
    }
    base_ctx.update(ctx)
    return render(template_name, request=request, **base_ctx)


# --------------- shared html check ---------------

def wants_html(request: Request) -> bool:
    if request.query_params.get("format") == "html":
        return True
    if request.headers.get("HX-Request", "").lower() == "true":
        return True
    return "text/html" in request.headers.get("accept", "").lower()
