from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.engine import get_connection
from app.main import create_app
from app.vault.markdown import parse_markdown_note


def _build_client(tmp_path: Path) -> tuple[TestClient, Settings]:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    app = create_app()
    app.state.settings = settings
    return TestClient(app), settings


def test_process_inbox_updates_markdown_and_reindexed_db(tmp_path: Path) -> None:
    client, settings = _build_client(tmp_path)

    migrate = client.post("/api/admin/migrate")
    assert migrate.status_code == 200

    first = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "Morning workout 5200 steps in 35 minutes and 320 calories.",
            "type": "activity",
            "tags": ["capture"],
        },
    )
    second = client.post(
        "/api/entries/capture",
        json={"raw_text": "second inbox entry", "type": "note", "tags": ["capture"]},
    )
    assert first.status_code == 200
    assert second.status_code == 200

    first_payload = first.json()
    second_payload = second.json()
    first_id = first_payload["entry_id"]
    second_id = second_payload["entry_id"]
    first_path = Path(first_payload["path"])
    second_path = Path(second_payload["path"])

    process = client.post(
        "/api/entries/process-inbox",
        json={"entry_ids": [first_id], "limit": 50},
    )
    assert process.status_code == 200
    process_payload = process.json()
    assert process_payload["selected_count"] == 1
    assert process_payload["processed_count"] == 1
    assert process_payload["processed_ids"] == [first_id]
    assert process_payload["failed_count"] == 0
    assert process_payload["failed_ids"] == []
    assert len(process_payload["run_ids"]) == 1
    assert process_payload["observations_indexed"] == 1
    assert process_payload["missing_paths"] == []

    first_parsed = parse_markdown_note(first_path.read_text(encoding="utf-8"))
    second_parsed = parse_markdown_note(second_path.read_text(encoding="utf-8"))
    first_fm = first_parsed.frontmatter
    second_fm = second_parsed.frontmatter
    assert first_fm["status"] == "processed"
    assert isinstance(first_fm.get("updated"), str) and first_fm["updated"]
    assert first_parsed.sections.get("Details", "").strip() != "-"
    actions_section = first_parsed.sections.get("Actions", "").strip()
    assert actions_section == "-" or actions_section.startswith("- [ ]")
    assert "Review and decide next action." not in actions_section
    assert second_fm["status"] == "inbox"

    conn = get_connection(settings)
    try:
        row_first = conn.execute(
            "SELECT status, updated_at FROM entries_index WHERE id = ?",
            (first_id,),
        ).fetchone()
        row_second = conn.execute(
            "SELECT status FROM entries_index WHERE id = ?",
            (second_id,),
        ).fetchone()
        run = conn.execute(
            "SELECT status, parse_ok FROM prompt_runs WHERE run_id = ?",
            (process_payload["run_ids"][0],),
        ).fetchone()
        obs = conn.execute(
            """
            SELECT steps, duration_min, calories, is_current
            FROM obs_activity
            WHERE entry_id = ?
            ORDER BY version_no DESC
            LIMIT 1
            """,
            (first_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row_first is not None
    assert row_first["status"] == "processed"
    assert row_first["updated_at"] == first_fm["updated"]
    assert row_second is not None
    assert row_second["status"] == "inbox"
    assert run is not None
    assert run["status"] == "success"
    assert run["parse_ok"] == 1
    assert obs is not None
    assert int(obs["steps"]) == 5200
    assert float(obs["duration_min"]) == 35.0
    assert float(obs["calories"]) == 320.0
    assert int(obs["is_current"]) == 1

    inbox = client.get("/api/entries/inbox")
    assert inbox.status_code == 200
    inbox_payload = inbox.json()
    assert inbox_payload["total"] == 1
    assert [item["id"] for item in inbox_payload["items"]] == [second_id]
