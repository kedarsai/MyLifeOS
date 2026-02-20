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


def test_search_api_returns_results_and_facets(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    a = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "alpha zenith project focus",
            "type": "note",
            "tags": ["focus"],
            "goals": ["goal-1"],
        },
    )
    b = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "beta zenith brainstorm",
            "type": "idea",
            "tags": ["brain"],
            "goals": ["goal-2"],
        },
    )
    c = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "gamma workout journal",
            "type": "note",
            "tags": ["focus"],
            "goals": ["goal-1"],
        },
    )
    assert a.status_code == 200
    assert b.status_code == 200
    assert c.status_code == 200

    search = client.get("/api/search", params={"q": "zenith"})
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert {"value": "note", "count": 1} in payload["facets"]["type"]
    assert {"value": "idea", "count": 1} in payload["facets"]["type"]
    assert {"value": "focus", "count": 1} in payload["facets"]["tags"]
    assert {"value": "brain", "count": 1} in payload["facets"]["tags"]

    filtered_type = client.get("/api/search", params={"q": "zenith", "type": "note"})
    assert filtered_type.status_code == 200
    type_payload = filtered_type.json()
    assert type_payload["total"] == 1
    assert type_payload["items"][0]["type"] == "note"

    filtered_tag = client.get("/api/search", params={"q": "zenith", "tag": "brain"})
    assert filtered_tag.status_code == 200
    tag_payload = filtered_tag.json()
    assert tag_payload["total"] == 1
    assert tag_payload["items"][0]["type"] == "idea"


def test_search_page_available(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    page = client.get("/search")
    assert page.status_code == 200
    assert "Search" in page.text


def test_search_html_includes_clickable_facets(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200
    assert (
        client.post(
            "/api/entries/capture",
            json={"raw_text": "zenith one", "type": "note", "tags": ["focus"], "goals": ["goal-1"]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/entries/capture",
            json={"raw_text": "zenith two", "type": "idea", "tags": ["brain"], "goals": ["goal-2"]},
        ).status_code
        == 200
    )

    html = client.get("/api/search", params={"format": "html", "q": "zenith"})
    assert html.status_code == 200
    body = html.text
    assert "facet-chip" in body
    assert "hx-get='/api/search?format=html&amp;q=zenith&amp;page=1&amp;page_size=20&amp;type=note'" in body
    assert "hx-get='/api/search?format=html&amp;q=zenith&amp;page=1&amp;page_size=20&amp;tag=focus'" in body
