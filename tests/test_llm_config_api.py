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
        LIFEOS_MODEL_INGEST="gpt-5-mini",
        LIFEOS_MODEL_DISTILL="gpt-5-mini",
        LIFEOS_MODEL_ANALYSIS="gpt-5.2",
        OPENAI_API_KEY="",
        OPENAI_BASE_URL="",
    )
    app = create_app()
    app.state.settings = settings
    return TestClient(app)


def test_llm_config_api_get_update_and_html(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    initial = client.get("/api/prompts/llm-config")
    assert initial.status_code == 200
    initial_payload = initial.json()
    assert initial_payload["model_ingest"] == "gpt-5-mini"
    assert initial_payload["model_analysis"] == "gpt-5.2"
    assert initial_payload["openai_api_key_configured"] is False

    update = client.post(
        "/api/prompts/llm-config",
        json={
            "model_ingest": "gpt-5-mini",
            "model_distill": "gpt-5-mini",
            "model_analysis": "gpt-5.2",
            "openai_base_url": "https://api.openai.com/v1",
            "openai_api_key": "sk-test-1234",
            "persist": False,
        },
    )
    assert update.status_code == 200
    updated_payload = update.json()
    assert updated_payload["ok"] is True
    assert updated_payload["persisted"] is False
    assert updated_payload["settings"]["openai_api_key_configured"] is True
    assert updated_payload["settings"]["openai_api_key_preview"].endswith("1234")

    html = client.get("/api/prompts/llm-config?format=html")
    assert html.status_code == 200
    assert "Save LLM Settings" in html.text
    assert "OPENAI_API_KEY configured" in html.text

    prompts_page = client.get("/prompts")
    assert prompts_page.status_code == 200
    assert "id=\"llm-config\"" in prompts_page.text
