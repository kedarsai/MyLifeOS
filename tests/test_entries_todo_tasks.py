from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _build_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
        OPENAI_API_KEY="",
        OPENAI_BASE_URL="",
    )
    app = create_app()
    app.state.settings = settings
    return TestClient(app)


def test_todo_entry_creates_concrete_task_title(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    capture = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "Buy milk tomorrow",
            "type": "todo",
        },
    )
    assert capture.status_code == 200
    entry_id = capture.json()["entry_id"]

    processed = client.post("/api/entries/process-inbox", json={"entry_ids": [entry_id], "limit": 5})
    assert processed.status_code == 200
    assert processed.json()["tasks_synced"] >= 1

    tasks = client.get("/api/tasks")
    assert tasks.status_code == 200
    items = tasks.json()["items"]
    titles = [str(item["title"]) for item in items]
    assert any("Buy milk tomorrow" in title for title in titles)
    assert "Review and decide next action." not in titles
    target = next(item for item in items if "Buy milk tomorrow" in str(item["title"]))
    expected = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    assert target["due_date"] == expected


def test_intent_entry_with_today_sets_due_date(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    capture = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "complete the value mapping of AR ASAP today - Hexagon project",
            "type": "note",
        },
    )
    assert capture.status_code == 200
    entry_id = capture.json()["entry_id"]

    processed = client.post("/api/entries/process-inbox", json={"entry_ids": [entry_id], "limit": 5})
    assert processed.status_code == 200
    assert processed.json()["tasks_synced"] >= 1

    tasks = client.get("/api/tasks")
    assert tasks.status_code == 200
    items = tasks.json()["items"]
    target = next(
        item
        for item in items
        if "value mapping of AR ASAP today - Hexagon project" in str(item["title"])
    )
    expected = datetime.now(timezone.utc).date().isoformat()
    assert target["due_date"] == expected
