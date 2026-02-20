from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.db.engine import get_connection


@dataclass
class MigrationResult:
    applied: list[str]
    skipped: list[str]


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _migrations_dir(project_root: Path) -> Path:
    return project_root / "migrations"


def apply_sql_migrations(project_root: Path, settings) -> MigrationResult:
    migrations_dir = _migrations_dir(project_root)
    migrations_dir.mkdir(parents=True, exist_ok=True)
    sql_files = sorted(migrations_dir.glob("*.sql"))

    conn = get_connection(settings)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              checksum TEXT NOT NULL,
              applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()

        applied: list[str] = []
        skipped: list[str] = []

        for path in sql_files:
            version = path.name
            sql = path.read_text(encoding="utf-8")
            checksum = _checksum(sql)

            row = conn.execute(
                "SELECT checksum FROM schema_migrations WHERE version = ?",
                (version,),
            ).fetchone()

            if row:
                if row["checksum"] != checksum:
                    raise RuntimeError(f"Migration checksum mismatch for {version}.")
                skipped.append(version)
                continue

            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                (version, checksum),
            )
            conn.commit()
            applied.append(version)

        return MigrationResult(applied=applied, skipped=skipped)
    finally:
        conn.close()

