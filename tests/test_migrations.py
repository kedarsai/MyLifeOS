from pathlib import Path

from app.core.config import Settings
from app.db.engine import get_connection
from app.db.migrations import apply_sql_migrations


def test_apply_sql_migrations_creates_core_tables(tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "migrations").mkdir(parents=True, exist_ok=True)
    source_sql = Path("migrations/0001_lifeos_v2.sql").read_text(encoding="utf-8")
    (project_root / "migrations" / "0001_lifeos_v2.sql").write_text(source_sql, encoding="utf-8")

    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    result = apply_sql_migrations(project_root, settings)
    assert "0001_lifeos_v2.sql" in result.applied

    conn = get_connection(settings)
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "artifact_runs" in tables
        assert "entries_index" in tables
        assert "tasks" in tables
    finally:
        conn.close()

