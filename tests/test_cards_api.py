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


def _create_card(settings, *, entity_type: str = "idea", entity_id: str = "idea-test") -> dict:
    from app.services.cards import save_card

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

    return save_card(
        settings,
        entity_type=entity_type,
        entity_id=entity_id,
        title="Test Insight",
        body_md="Key takeaway from conversation.",
        source_run_id=run_id,
        tags=["ai", "insight"],
    )


def test_cards_list_empty(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200
    res = client.get("/api/cards")
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_card_create_and_detail(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    card = _create_card(client.app.state.settings)
    card_id = card["card_id"]

    res = client.get(f"/api/cards/{card_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["card_id"] == card_id
    assert detail["title"] == "Test Insight"
    assert detail["entity_type"] == "idea"
    assert detail["tags"] == ["ai", "insight"]


def test_cards_filter_by_entity(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    settings = client.app.state.settings
    _create_card(settings, entity_type="idea", entity_id="idea-1")
    _create_card(settings, entity_type="goal", entity_id="goal-1")

    # Filter by entity_type
    res = client.get("/api/cards", params={"entity_type": "idea"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    # Filter by entity_type and entity_id
    res = client.get("/api/cards", params={"entity_type": "goal", "entity_id": "goal-1"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    # All cards
    res = client.get("/api/cards")
    assert res.status_code == 200
    assert len(res.json()["items"]) == 2


def test_card_not_found(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200
    res = client.get("/api/cards/nonexistent")
    assert res.status_code == 404


def test_cards_search(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    settings = client.app.state.settings
    _create_card(settings)

    res = client.get("/api/cards", params={"q": "takeaway"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    res = client.get("/api/cards", params={"q": "nonexistent_term"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0
