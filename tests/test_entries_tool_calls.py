from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.entries import _apply_ingest_tool_calls
from app.main import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )


def _build_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
        OPENAI_API_KEY="sk-test",
    )
    app = create_app()
    app.state.settings = settings
    return TestClient(app)


def test_apply_ingest_tool_calls_resolve_relative_due_date(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    actions = [{"title": "Complete mapping", "priority": "medium"}]
    out = _apply_ingest_tool_calls(
        actions,
        tool_calls=[
            {
                "name": "resolve_relative_due_date",
                "arguments": {"action_index": 0, "offset_days": 0},
            }
        ],
        settings=settings,
    )
    expected = datetime.now(timezone.utc).date().isoformat()
    assert out[0]["due_date"] == expected


def test_apply_ingest_tool_calls_set_due_date(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    actions = [{"title": "Ship V1", "priority": "high"}]
    out = _apply_ingest_tool_calls(
        actions,
        tool_calls=[
            {
                "name": "set_due_date",
                "arguments": {"action_index": 0, "date": "2026-02-21"},
            }
        ],
        settings=settings,
    )
    assert out[0]["due_date"] == "2026-02-21"


def test_apply_ingest_tool_calls_ignores_invalid_call(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    actions = [{"title": "Draft proposal", "priority": "medium"}]
    out = _apply_ingest_tool_calls(
        actions,
        tool_calls=[
            {
                "name": "resolve_relative_due_date",
                "arguments": {"action_index": 0},
            }
        ],
        settings=settings,
    )
    assert "due_date" not in out[0]


def test_process_inbox_applies_tool_calls_from_llm(monkeypatch, tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    captured = client.post(
        "/api/entries/capture",
        json={"raw_text": "complete value mapping today", "type": "note"},
    )
    assert captured.status_code == 200
    entry_id = captured.json()["entry_id"]

    def fake_run_openai_json_prompt(*args, **kwargs):
        return {
            "entry_type": "note",
            "summary": "complete value mapping today",
            "details_bullets": ["Complete value mapping."],
            "tags": [],
            "goal_links": [],
            "observations": {
                "activity": [],
                "sleep": [],
                "food": [],
                "weight": [],
            },
            "actions": [{"title": "complete value mapping today", "priority": "medium", "status": "open"}],
            "tool_calls": [
                {
                    "name": "resolve_relative_due_date",
                    "arguments": {"action_index": 0, "offset_days": 0},
                }
            ],
            "needs_followup": False,
            "followup_questions": [],
            "confidence": 0.9,
        }

    monkeypatch.setattr("app.services.entries.run_openai_json_prompt", fake_run_openai_json_prompt)

    processed = client.post("/api/entries/process-inbox", json={"entry_ids": [entry_id], "limit": 5})
    assert processed.status_code == 200
    assert processed.json()["tasks_synced"] >= 1

    tasks = client.get("/api/tasks")
    assert tasks.status_code == 200
    items = tasks.json()["items"]
    target = next(item for item in items if "complete value mapping today" in str(item["title"]))
    expected = datetime.now(timezone.utc).date().isoformat()
    assert target["due_date"] == expected
