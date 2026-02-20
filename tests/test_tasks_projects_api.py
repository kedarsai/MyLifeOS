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


def test_tasks_and_projects_filters_and_assignment(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    goal_res = client.post(
        "/api/goals",
        json={
            "name": "Launch goal",
            "start_date": "2026-02-19",
            "metrics": ["steps"],
            "status": "active",
            "review_cadence_days": 7,
        },
    )
    assert goal_res.status_code == 200
    goal_id = goal_res.json()["goal_id"]

    project_res = client.post(
        "/api/projects",
        json={"name": "Client Alpha", "kind": "client", "status": "active", "notes": "Website build"},
    )
    assert project_res.status_code == 200
    project_id = project_res.json()["project_id"]

    capture = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "Built first feature. TODO: ship v1 due:2026-02-20",
            "type": "note",
            "goals": [goal_id],
        },
    )
    assert capture.status_code == 200
    entry_id = capture.json()["entry_id"]

    assert client.post(f"/api/goals/{goal_id}/link-entry", json={"entry_id": entry_id}).status_code == 200
    processed = client.post("/api/entries/process-inbox", json={"entry_ids": [entry_id], "limit": 10})
    assert processed.status_code == 200

    tasks = client.get("/api/tasks")
    assert tasks.status_code == 200
    items = tasks.json()["items"]
    assert len(items) >= 1
    task = items[0]
    assert task["goal_id"] == goal_id

    assigned = client.post(f"/api/tasks/{task['task_id']}/project", json={"project_id": project_id})
    assert assigned.status_code == 200

    filtered = client.get("/api/tasks", params={"project_id": project_id})
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 1
    assert filtered.json()["items"][0]["project_id"] == project_id

    complete_html = client.post(
        f"/api/tasks/{task['task_id']}/complete",
        params={"format": "html", "view": "tasks"},
    )
    assert complete_html.status_code == 200

    deleted = client.post(f"/api/tasks/{task['task_id']}/delete")
    assert deleted.status_code == 200
    remaining = client.get("/api/tasks")
    assert remaining.status_code == 200
    assert all(item["task_id"] != task["task_id"] for item in remaining.json()["items"])

    assert client.get("/tasks").status_code == 200
    assert client.get("/projects").status_code == 200
