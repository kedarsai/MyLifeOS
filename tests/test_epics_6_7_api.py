from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _build_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    app = create_app()
    app.state.settings = settings
    return TestClient(app)


def test_goals_today_and_improvements_flow(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    goal = client.post(
        "/api/goals",
        json={
            "name": "Build consistency",
            "start_date": "2026-02-19",
            "metrics": ["steps", "sleep"],
            "status": "active",
            "review_cadence_days": 7,
        },
    )
    assert goal.status_code == 200
    goal_id = goal.json()["goal_id"]

    captured = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "Workout done. TODO: stretch for 10 minutes due:2026-02-19. Need to improve recovery.",
            "type": "activity",
            "goals": [goal_id],
        },
    )
    assert captured.status_code == 200
    entry_id = captured.json()["entry_id"]

    linked = client.post(f"/api/goals/{goal_id}/link-entry", json={"entry_id": entry_id})
    assert linked.status_code == 200

    processed = client.post("/api/entries/process-inbox", json={"entry_ids": [entry_id], "limit": 20})
    assert processed.status_code == 200
    p = processed.json()
    assert p["processed_count"] == 1
    assert p["tasks_synced"] >= 1
    assert p["observations_indexed"] >= 1
    assert p["improvements_created"] >= 1

    today = client.get("/api/today")
    assert today.status_code == 200
    today_payload = today.json()
    total_tasks = (
        len(today_payload["due_today"])
        + len(today_payload["overdue"])
        + len(today_payload["next_actions"])
    )
    assert total_tasks >= 1

    first_task = (
        today_payload["due_today"][:1]
        + today_payload["overdue"][:1]
        + today_payload["next_actions"][:1]
    )[0]
    done = client.post(f"/api/tasks/{first_task['task_id']}/complete")
    assert done.status_code == 200

    dashboard = client.get(f"/api/goals/{goal_id}/dashboard")
    assert dashboard.status_code == 200
    d = dashboard.json()
    assert d["goal"]["goal_id"] == goal_id
    assert "steps_avg_7d" in d["metrics"]

    improvements = client.get("/api/improvements")
    assert improvements.status_code == 200
    assert improvements.json()["total"] >= 1
