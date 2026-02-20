from pathlib import Path

from fastapi import APIRouter, Request

from app.db.migrations import apply_sql_migrations
from app.services.indexer import VaultIndexer
from app.vault.manager import VaultManager

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@router.post("/migrate")
def migrate(request: Request) -> dict:
    settings = request.app.state.settings
    result = apply_sql_migrations(_project_root(), settings)
    return {"applied": result.applied, "skipped": result.skipped}


@router.post("/rebuild-index")
def rebuild_index(request: Request) -> dict:
    settings = request.app.state.settings
    VaultManager(settings).ensure_layout()
    apply_sql_migrations(_project_root(), settings)
    stats = VaultIndexer(settings).rebuild()
    return {
        "files_scanned": stats.files_scanned,
        "entries_indexed": stats.entries_indexed,
        "tasks_indexed": stats.tasks_indexed,
        "improvements_indexed": stats.improvements_indexed,
        "insights_indexed": stats.insights_indexed,
        "chats_indexed": stats.chats_indexed,
        "goals_indexed": stats.goals_indexed,
    }

