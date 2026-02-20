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


def test_dashboard_summary_and_page(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    cap = client.post(
        "/api/entries/capture",
        json={"raw_text": "dashboard smoke", "type": "note"},
    )
    assert cap.status_code == 200

    summary = client.get("/api/dashboard/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert "entries" in payload
    assert "runs" in payload
    assert "conflicts" in payload
    assert isinstance(payload["recent_entries"], list)
    assert isinstance(payload["recent_runs"], list)

    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/dashboard"

    page = client.get("/dashboard")
    assert page.status_code == 200
    assert "Dashboard" in page.text
