from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import Settings


def get_connection(settings: Settings) -> sqlite3.Connection:
    db_path: Path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

