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


def test_ideas_list_empty(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200
    res = client.get("/api/ideas")
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_idea_create_and_get(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    res = client.post("/api/ideas", json={"title": "Build a sleep tracker", "description": "Track sleep quality"})
    assert res.status_code == 200
    idea = res.json()
    assert idea["title"] == "Build a sleep tracker"
    assert idea["status"] == "raw"
    assert idea["description"] == "Track sleep quality"
    idea_id = idea["idea_id"]

    # Get detail
    res = client.get(f"/api/ideas/{idea_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["idea_id"] == idea_id
    assert "entries" in detail


def test_idea_status_transitions(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    res = client.post("/api/ideas", json={"title": "Test idea"})
    assert res.status_code == 200
    idea_id = res.json()["idea_id"]

    # Update to exploring
    res = client.patch(f"/api/ideas/{idea_id}", json={"status": "exploring"})
    assert res.status_code == 200
    new_idea = res.json()
    assert new_idea["status"] == "exploring"
    # Versioned: new idea_id
    assert new_idea["idea_id"] != idea_id
    assert new_idea["version_no"] == 2

    # Update to mature
    res = client.patch(f"/api/ideas/{new_idea['idea_id']}", json={"status": "mature"})
    assert res.status_code == 200
    assert res.json()["status"] == "mature"
    assert res.json()["version_no"] == 3


def test_idea_filter_by_status(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    client.post("/api/ideas", json={"title": "Raw idea"})
    res = client.post("/api/ideas", json={"title": "Exploring idea"})
    exploring_id = res.json()["idea_id"]
    client.patch(f"/api/ideas/{exploring_id}", json={"status": "exploring"})

    # Filter raw
    res = client.get("/api/ideas", params={"status": "raw"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["title"] == "Raw idea"

    # Filter exploring
    res = client.get("/api/ideas", params={"status": "exploring"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["title"] == "Exploring idea"


def test_idea_convert_to_goal(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    res = client.post("/api/ideas", json={"title": "Become a runner"})
    assert res.status_code == 200
    idea_id = res.json()["idea_id"]

    # Convert to goal
    res = client.post(
        f"/api/ideas/{idea_id}/convert",
        json={"target_type": "goal", "start_date": "2026-03-01"},
    )
    assert res.status_code == 200
    result = res.json()
    assert result["converted_to_type"] == "goal"
    assert result["converted_to_id"] is not None
    assert result["idea"]["status"] == "converted"

    # Verify the goal was created
    goal_id = result["converted_to_id"]
    goal = client.get(f"/api/goals/{goal_id}")
    assert goal.status_code == 200
    assert goal.json()["name"] == "Become a runner"


def test_idea_convert_to_project(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    res = client.post("/api/ideas", json={"title": "Side project MVP"})
    assert res.status_code == 200
    idea_id = res.json()["idea_id"]

    res = client.post(
        f"/api/ideas/{idea_id}/convert",
        json={"target_type": "project", "kind": "personal"},
    )
    assert res.status_code == 200
    assert res.json()["converted_to_type"] == "project"


def test_idea_not_found(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200
    res = client.get("/api/ideas/nonexistent")
    assert res.status_code == 404


def test_entry_detail_found_and_not_found(tmp_path: Path) -> None:
    """GET /api/entries/{entry_id} returns full entry or 404."""
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    # Capture an entry so one exists
    res = client.post(
        "/api/entries/capture",
        json={"raw_text": "Test raw content", "type": "note"},
    )
    assert res.status_code == 200
    entry_id = res.json()["entry_id"]

    # Fetch detail
    res = client.get(f"/api/entries/{entry_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == entry_id
    assert detail["raw_text"] == "Test raw content"
    assert "details_md" in detail
    assert "actions_md" in detail
    assert "tags" in detail

    # 404 for missing
    res = client.get("/api/entries/nonexistent-id")
    assert res.status_code == 404


def test_idea_entry_note_update(tmp_path: Path) -> None:
    """PATCH /api/ideas/{id}/entries/{eid} updates note, 404 for missing link."""
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    # Create an idea and capture an entry, then link them
    res = client.post("/api/ideas", json={"title": "Note test idea"})
    assert res.status_code == 200
    idea_id = res.json()["idea_id"]

    res = client.post(
        "/api/entries/capture",
        json={"raw_text": "Entry for note test", "type": "idea"},
    )
    assert res.status_code == 200
    entry_id = res.json()["entry_id"]

    # Link the entry to the idea via service directly
    from app.services.ideas import link_entry_to_idea, _ensure_run_global
    import uuid
    run_id = f"test-{uuid.uuid4()}"
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    _ensure_run_global(settings, run_id)
    link_entry_to_idea(
        settings, idea_id=idea_id, entry_id=entry_id,
        link_type="related", source_run_id=run_id,
    )

    # Update note via PATCH
    res = client.patch(
        f"/api/ideas/{idea_id}/entries/{entry_id}",
        json={"note": "This is a context note"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["note"] == "This is a context note"

    # Verify note shows in idea detail
    res = client.get(f"/api/ideas/{idea_id}")
    assert res.status_code == 200
    entries = res.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["note"] == "This is a context note"

    # 404 for non-existent link
    res = client.patch(
        f"/api/ideas/{idea_id}/entries/nonexistent-entry",
        json={"note": "nope"},
    )
    assert res.status_code == 404
