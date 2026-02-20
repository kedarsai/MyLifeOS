from __future__ import annotations

import uuid
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


def _setup_topic(settings) -> tuple[str, str]:
    """Create an area and topic, return (area_id, topic_id)."""
    from app.services.topics import get_or_create_area, get_or_create_topic

    run_id = f"test-{uuid.uuid4()}"
    from app.db.engine import get_connection
    conn = get_connection(settings)
    try:
        conn.execute(
            "INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json, created_at) "
            "VALUES (?, 'system', 'test', '{}', datetime('now'))",
            (run_id,),
        )
        conn.commit()
    finally:
        conn.close()

    area = get_or_create_area(settings, name="Tech", source_run_id=run_id)
    topic = get_or_create_topic(
        settings, area_id=area["area_id"], name="LLMs", source_run_id=run_id,
    )
    return area["area_id"], topic["topic_id"]


def test_thread_with_entity_type(tmp_path: Path) -> None:
    """Create a chat thread linked to a thought_topic."""
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    _, topic_id = _setup_topic(client.app.state.settings)

    res = client.post(
        "/api/chat/threads",
        json={"title": "Discuss LLMs", "entity_type": "thought_topic", "entity_id": topic_id},
    )
    assert res.status_code == 200
    thread = res.json()
    assert thread["entity_type"] == "thought_topic"
    assert thread["entity_id"] == topic_id


def test_thread_list_filter_entity(tmp_path: Path) -> None:
    """Filter thread list by entity_type and entity_id."""
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    _, topic_id = _setup_topic(client.app.state.settings)

    client.post(
        "/api/chat/threads",
        json={"title": "Topic thread", "entity_type": "thought_topic", "entity_id": topic_id},
    )
    client.post("/api/chat/threads", json={"title": "Generic thread"})

    # All threads
    res = client.get("/api/chat/threads")
    assert res.status_code == 200
    assert len(res.json()["items"]) == 2

    # Filter by entity_type
    res = client.get("/api/chat/threads", params={"entity_type": "thought_topic", "entity_id": topic_id})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["entity_type"] == "thought_topic"


def test_entity_chat_context(tmp_path: Path) -> None:
    """Build context for a topic-scoped chat."""
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    _, topic_id = _setup_topic(client.app.state.settings)

    res = client.get(
        "/api/chat/context",
        params={"entity_type": "thought_topic", "entity_id": topic_id},
    )
    assert res.status_code == 200
    ctx = res.json()
    assert ctx["entity"] is not None
    assert "cards" in ctx


def test_goal_backward_compat(tmp_path: Path) -> None:
    """Threads created with goal_id still work with entity_type."""
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    goal_res = client.post(
        "/api/goals",
        json={"name": "Test goal", "start_date": "2026-01-01"},
    )
    assert goal_res.status_code == 200
    goal_id = goal_res.json()["goal_id"]

    res = client.post(
        "/api/chat/threads",
        json={"title": "Goal discussion", "goal_id": goal_id},
    )
    assert res.status_code == 200
    thread = res.json()
    assert thread["goal_id"] == goal_id
    assert thread["entity_type"] == "goal"
    assert thread["entity_id"] == goal_id


def test_confirm_action_create_task(tmp_path: Path) -> None:
    """Execute a proposed action to create a task."""
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    goal_res = client.post(
        "/api/goals",
        json={"name": "Test goal", "start_date": "2026-01-01"},
    )
    goal_id = goal_res.json()["goal_id"]

    thread_res = client.post(
        "/api/chat/threads",
        json={"title": "Coach me", "goal_id": goal_id},
    )
    thread_id = thread_res.json()["thread_id"]

    # Add a user message
    client.post(
        f"/api/chat/threads/{thread_id}/messages",
        json={"role": "user", "content": "What should I do next?"},
    )

    res = client.post(
        f"/api/chat/threads/{thread_id}/confirm-action",
        json={
            "action_type": "create_task",
            "label": "Run 5k tomorrow",
            "params": {"title": "Run 5k tomorrow"},
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_confirm_action_unknown_type(tmp_path: Path) -> None:
    """Unknown action type returns 422."""
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    thread_res = client.post("/api/chat/threads", json={"title": "Test"})
    thread_id = thread_res.json()["thread_id"]

    res = client.post(
        f"/api/chat/threads/{thread_id}/confirm-action",
        json={"action_type": "bogus", "label": "x", "params": {}},
    )
    assert res.status_code == 422
