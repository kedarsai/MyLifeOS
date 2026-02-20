from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes_admin import router as admin_router
from app.api.routes_chat import router as chat_router
from app.api.routes_conflicts import router as conflicts_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_entries import router as entries_router
from app.api.routes_goals import router as goals_router
from app.api.routes_health import router as health_router
from app.api.routes_improvements import router as improvements_router
from app.api.routes_prompts import router as prompts_router
from app.api.routes_projects import router as projects_router
from app.api.routes_reminders import router as reminders_router
from app.api.routes_reviews import router as reviews_router
from app.api.routes_runs import router as runs_router
from app.api.routes_search import router as search_router
from app.api.routes_tasks import tasks_router, today_router
from app.api.routes_thoughts import router as thoughts_router
from app.api.routes_ideas import router as ideas_router
from app.api.routes_cards import router as cards_router
from app.core.config import get_settings
from app.db.migrations import apply_sql_migrations
from app.services.prompts import ensure_default_prompt_assets, load_prompt_templates
from app.ui.routes_pages import router as ui_router
from app.vault.manager import VaultManager


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_settings = app.state.settings
        VaultManager(active_settings).ensure_layout()
        apply_sql_migrations(Path(__file__).resolve().parents[1], active_settings)
        ensure_default_prompt_assets(active_settings)
        app.state.prompt_reload = load_prompt_templates(active_settings)
        yield

    app = FastAPI(title="LifeOS API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    _static_dir = Path(__file__).resolve().parent / "static"
    if _static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
    app.include_router(health_router)
    app.include_router(admin_router)
    app.include_router(dashboard_router)
    app.include_router(entries_router)
    app.include_router(goals_router)
    app.include_router(chat_router)
    app.include_router(improvements_router)
    app.include_router(search_router)
    app.include_router(prompts_router)
    app.include_router(projects_router)
    app.include_router(reminders_router)
    app.include_router(reviews_router)
    app.include_router(runs_router)
    app.include_router(tasks_router)
    app.include_router(today_router)
    app.include_router(conflicts_router)
    app.include_router(thoughts_router)
    app.include_router(ideas_router)
    app.include_router(cards_router)
    app.include_router(ui_router)

    # --- SPA catch-all (only when frontend/dist exists) ---
    _frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if _frontend_dist.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_frontend_dist / "assets")),
            name="spa-assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_catch_all(full_path: str):
            from fastapi.responses import FileResponse

            file_path = _frontend_dist / full_path
            if file_path.is_file() and ".." not in full_path:
                return FileResponse(str(file_path))
            return FileResponse(str(_frontend_dist / "index.html"))

    return app


app = create_app()
