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


def _setup_area_and_topic(client: TestClient) -> tuple[str, str]:
    """Helper: create an area and topic via the service layer, returns (area_id, topic_id)."""
    import uuid
    from app.services.topics import get_or_create_area, get_or_create_topic

    settings = client.app.state.settings
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

    area = get_or_create_area(settings, name="Technology", source_run_id=run_id)
    topic = get_or_create_topic(
        settings, area_id=area["area_id"], name="AI & Humanity", source_run_id=run_id,
    )
    return area["area_id"], topic["topic_id"]


def test_areas_list_empty(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200
    res = client.get("/api/thoughts/areas")
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_areas_and_topics_crud(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    area_id, topic_id = _setup_area_and_topic(client)

    # List areas
    res = client.get("/api/thoughts/areas")
    assert res.status_code == 200
    areas = res.json()["items"]
    assert len(areas) == 1
    assert areas[0]["name"] == "Technology"
    assert areas[0]["topic_count"] == 1

    # List topics in area
    res = client.get(f"/api/thoughts/areas/{area_id}/topics")
    assert res.status_code == 200
    topics = res.json()["items"]
    assert len(topics) == 1
    assert topics[0]["name"] == "AI & Humanity"

    # Topic detail
    res = client.get(f"/api/thoughts/topics/{topic_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["topic_id"] == topic_id
    assert detail["name"] == "AI & Humanity"
    assert "entries" in detail


def test_topic_not_found(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200
    res = client.get("/api/thoughts/topics/nonexistent")
    assert res.status_code == 404


def test_heatmap_empty(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200
    res = client.get("/api/thoughts/heatmap")
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_topic_with_linked_entry(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    # Capture an entry
    capture = client.post(
        "/api/entries/capture",
        json={"raw_text": "AI is transforming healthcare", "type": "thought"},
    )
    assert capture.status_code == 200
    entry_id = capture.json()["entry_id"]

    # Create area + topic + link
    import uuid
    from app.services.topics import get_or_create_area, get_or_create_topic, assign_entry_topic

    settings = client.app.state.settings
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

    area = get_or_create_area(settings, name="Technology", source_run_id=run_id)
    topic = get_or_create_topic(
        settings, area_id=area["area_id"], name="AI & Healthcare", source_run_id=run_id,
    )
    assign_entry_topic(
        settings, entry_id=entry_id, topic_id=topic["topic_id"], source_run_id=run_id,
    )

    # Check topic detail has the entry
    res = client.get(f"/api/thoughts/topics/{topic['topic_id']}")
    assert res.status_code == 200
    detail = res.json()
    assert len(detail["entries"]) == 1
    assert detail["entries"][0]["id"] == entry_id
