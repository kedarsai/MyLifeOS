from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.db.migrations import apply_sql_migrations
from app.services.prompts import list_prompt_templates, load_prompt_templates


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_prompt_templates_from_yaml_and_reload(tmp_path: Path) -> None:
    vault = tmp_path / "Vault"
    settings = Settings(
        LIFEOS_VAULT_PATH=str(vault),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    apply_sql_migrations(Path.cwd(), settings)

    _write(
        vault / "config/prompts/schemas/ingest_extract.json",
        '{"type":"object","properties":{"summary":{"type":"string"}},"required":["summary"]}',
    )
    _write(
        vault / "config/prompts/ingest_extract.yaml",
        """id: ingest_extract
version: v1
provider: openai
model: gpt-5-mini
params:
  temperature: 0.2
schema: schemas/ingest_extract.json
system: |
  System prompt text.
user: |
  User prompt text.
""",
    )

    first = load_prompt_templates(settings)
    assert first.loaded == 1
    assert first.errors == []

    listed = list_prompt_templates(settings, limit=20, offset=0)
    assert listed["total"] == 1
    assert listed["items"][0]["prompt_id"] == "ingest_extract"
    assert listed["items"][0]["model"] == "gpt-5-mini"

    _write(
        vault / "config/prompts/ingest_extract.yaml",
        """id: ingest_extract
version: v1
provider: openai
model: gpt-5.2
params:
  temperature: 0.1
schema: schemas/ingest_extract.json
system: |
  Updated system prompt.
user: |
  Updated user prompt.
""",
    )

    second = load_prompt_templates(settings)
    assert second.loaded == 1
    assert second.errors == []

    listed_after = list_prompt_templates(settings, limit=20, offset=0)
    assert listed_after["total"] == 1
    assert listed_after["items"][0]["model"] == "gpt-5.2"
    assert listed_after["items"][0]["params"]["temperature"] == 0.1
