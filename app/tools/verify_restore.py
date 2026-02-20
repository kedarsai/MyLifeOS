from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.vault.markdown import parse_markdown_note


def _count_vault(vault_path: Path) -> dict[str, int]:
    counts = {
        "entries": 0,
        "tasks": 0,
        "improvements": 0,
        "insights": 0,
        "chat_threads": 0,
    }
    for path in vault_path.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        parsed = parse_markdown_note(text)
        fm = parsed.frontmatter
        if not fm:
            continue
        entity_type = str(fm.get("entity_type") or "").strip().lower()
        if entity_type == "task":
            counts["tasks"] += 1
            continue
        if entity_type == "improvement":
            counts["improvements"] += 1
            continue
        if entity_type == "insight":
            counts["insights"] += 1
            continue
        if entity_type == "chat_thread":
            counts["chat_threads"] += 1
            continue
        if "id" in fm and "type" in fm:
            counts["entries"] += 1
    return counts


def _count_db(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        out = {}
        out["entries"] = conn.execute("SELECT COUNT(*) FROM entries_index").fetchone()[0]
        out["tasks"] = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        out["improvements"] = conn.execute("SELECT COUNT(*) FROM improvements").fetchone()[0]
        out["insights"] = conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
        out["chat_threads"] = conn.execute("SELECT COUNT(*) FROM chat_threads").fetchone()[0]
        open_conflicts = conn.execute(
            "SELECT COUNT(*) FROM sync_conflicts WHERE conflict_status = 'open'"
        ).fetchone()[0]
        out["open_conflicts"] = open_conflicts
        return out
    finally:
        conn.close()


def run(vault: Path, db: Path) -> int:
    vault_counts = _count_vault(vault)
    db_counts = _count_db(db)

    failures: list[str] = []
    for key in ("entries", "tasks", "improvements", "insights", "chat_threads"):
        if vault_counts[key] != db_counts[key]:
            failures.append(f"{key}: vault={vault_counts[key]} db={db_counts[key]}")
    if db_counts["open_conflicts"] != 0:
        failures.append(f"open_conflicts: {db_counts['open_conflicts']}")

    print("vault_counts:", vault_counts)
    print("db_counts:", db_counts)
    if failures:
        print("restore verification failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("restore verification passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify restore consistency between vault and DB.")
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    args = parser.parse_args()
    return run(args.vault, args.db)


if __name__ == "__main__":
    raise SystemExit(main())

