from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.llm_config import update_llm_runtime_config


def test_update_llm_runtime_config_persists_env_and_supports_clear_key(tmp_path: Path) -> None:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    env_path = tmp_path / ".env"

    updated = update_llm_runtime_config(
        settings,
        model_ingest="gpt-5-mini",
        model_distill="gpt-5-mini",
        model_analysis="gpt-5.2",
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="sk-local-9999",
        persist=True,
        env_path=env_path,
    )
    assert updated["openai_api_key_configured"] is True
    text = env_path.read_text(encoding="utf-8")
    assert "LIFEOS_MODEL_INGEST=gpt-5-mini" in text
    assert "LIFEOS_MODEL_ANALYSIS=gpt-5.2" in text
    assert "OPENAI_API_KEY=sk-local-9999" in text

    cleared = update_llm_runtime_config(
        settings,
        model_ingest="gpt-5-mini",
        model_distill="gpt-5-mini",
        model_analysis="gpt-5.2",
        clear_api_key=True,
        persist=True,
        env_path=env_path,
    )
    assert cleared["openai_api_key_configured"] is False
    cleared_text = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=" in cleared_text
