from __future__ import annotations

import json
import uuid
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


def _insert_conflict(
    settings: Settings,
    *,
    conflict_id: str,
    entity_id: str,
    path: str,
    app_run_id: str,
    details: dict,
) -> None:
    conn = get_connection(settings)
    try:
        conn.execute(
            """
            INSERT INTO sync_conflicts (
              conflict_id, entity_type, entity_id, logical_id, path, app_run_id,
              vault_content_hash, vault_hash_version, db_content_hash, db_hash_version,
              conflict_status, details_json, created_at
            )
            VALUES (?, 'entry', ?, ?, ?, ?, ?, 'sha256-v1', ?, 'sha256-v1', 'open', ?, ?)
            """,
            (
                conflict_id,
                entity_id,
                entity_id,
                path,
                app_run_id,
                "vault-hash",
                "db-hash",
                json.dumps(details),
                "2026-02-19T12:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO sync_conflict_events (
              event_id, conflict_id, action, actor, source_run_id, notes, created_at
            )
            VALUES (?, ?, 'opened', 'local_user', ?, 'seed', '2026-02-19T12:00:00+00:00')
            """,
            (str(uuid.uuid4()), conflict_id, app_run_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_conflict_center_keep_app_resolution_end_to_end(tmp_path: Path) -> None:
    client, settings = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    captured = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "vault text from capture",
            "type": "note",
            "tags": ["capture"],
        },
    )
    assert captured.status_code == 200
    payload = captured.json()

    conflict_id = "conflict-keep-app"
    _insert_conflict(
        settings,
        conflict_id=conflict_id,
        entity_id=payload["entry_id"],
        path=payload["path"],
        app_run_id=payload["source_run_id"],
        details={
            "summary": "app version should win",
            "app_snapshot": {
                "id": payload["entry_id"],
                "type": "note",
                "status": "processed",
                "summary": "App summary",
                "raw_text": "app raw text",
                "details_md": "app details",
                "actions_md": "- [ ] app action",
                "tags": ["app"],
                "goals": [],
                "source_run_id": payload["source_run_id"],
            },
        },
    )

    badge = client.get("/api/conflicts/badge")
    assert badge.status_code == 200
    assert badge.json()["open_count"] == 1

    page = client.get("/conflicts")
    assert page.status_code == 200
    assert "Conflict Center" in page.text

    listed = client.get("/api/conflicts", params={"status": "open"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["conflict_id"] == conflict_id

    detail = client.get(f"/api/conflicts/{conflict_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["conflict_status"] == "open"
    assert "vault" in detail_payload["diff_text"]
    assert "app" in detail_payload["diff_text"]

    resolved = client.post(
        f"/api/conflicts/{conflict_id}/resolve",
        json={"action": "keep_app", "actor": "local_user"},
    )
    assert resolved.status_code == 200
    resolved_payload = resolved.json()
    assert resolved_payload["conflict_status"] == "resolved_keep_app"

    parsed = parse_markdown_note(Path(payload["path"]).read_text(encoding="utf-8"))
    assert parsed.frontmatter["status"] == "processed"
    assert parsed.frontmatter["summary"] == "App summary"
    assert parsed.sections["Context (Raw)"] == "app raw text"

    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT conflict_status, resolved_at FROM sync_conflicts WHERE conflict_id = ?",
            (conflict_id,),
        ).fetchone()
        events = conn.execute(
            "SELECT action FROM sync_conflict_events WHERE conflict_id = ? ORDER BY created_at",
            (conflict_id,),
        ).fetchall()
    finally:
        conn.close()

    assert row is not None
    assert row["conflict_status"] == "resolved_keep_app"
    assert row["resolved_at"]
    assert [event["action"] for event in events][-1] == "resolved_keep_app"

    badge_after = client.get("/api/conflicts/badge")
    assert badge_after.status_code == 200
    assert badge_after.json()["open_count"] == 0


def test_conflict_center_merge_persists_merge_metadata(tmp_path: Path) -> None:
    client, settings = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    captured = client.post(
        "/api/entries/capture",
        json={"raw_text": "vault line", "type": "note"},
    )
    assert captured.status_code == 200
    payload = captured.json()
    path = Path(payload["path"])

    # Simulate external vault edit before conflict resolution.
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("vault line", "vault-only line"), encoding="utf-8")

    conflict_id = "conflict-merge"
    _insert_conflict(
        settings,
        conflict_id=conflict_id,
        entity_id=payload["entry_id"],
        path=payload["path"],
        app_run_id=payload["source_run_id"],
        details={
            "summary": "merge needed",
            "app_snapshot": {
                "id": payload["entry_id"],
                "type": "note",
                "status": "processed",
                "summary": "merged summary",
                "raw_text": "app-only line",
                "details_md": "db details",
                "actions_md": "- [ ] db action",
                "tags": ["db"],
                "goals": [],
                "source_run_id": payload["source_run_id"],
            },
        },
    )

    resolved = client.post(
        f"/api/conflicts/{conflict_id}/resolve",
        json={"action": "merge", "actor": "local_user"},
    )
    assert resolved.status_code == 200
    resolved_payload = resolved.json()
    assert resolved_payload["conflict_status"] == "resolved_merged"
    assert "merge_metadata" in resolved_payload["details"]

    merged_text = path.read_text(encoding="utf-8")
    assert "vault-only line" in merged_text
    assert "app-only line" in merged_text
    assert "--- merged ---" in merged_text
