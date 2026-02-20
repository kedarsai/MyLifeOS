from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_client(tmp_path: Path) -> tuple[TestClient, Path]:
    vault = tmp_path / "Vault"
    settings = Settings(
        LIFEOS_VAULT_PATH=str(vault),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    app = create_app()
    app.state.settings = settings
    return TestClient(app), vault


def test_prompts_api_reload_and_list(tmp_path: Path) -> None:
    client, vault = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    _write(
        vault / "config/prompts/schemas/weekly_goal_review.json",
        '{"type":"object","properties":{"title":{"type":"string"}}}',
    )
    _write(
        vault / "config/prompts/weekly_goal_review.yaml",
        """id: weekly_goal_review
version: v1
provider: openai
model: gpt-5.2
params:
  temperature: 0.1
schema: schemas/weekly_goal_review.json
system: |
  You are a review assistant.
user: |
  Summarize this week.
""",
    )

    reload_resp = client.post("/api/prompts/reload")
    assert reload_resp.status_code == 200
    payload = reload_resp.json()
    assert payload["loaded"] == 1
    assert payload["errors"] == []
    assert payload["total"] == 1

    listed = client.get("/api/prompts")
    assert listed.status_code == 200
    list_payload = listed.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["prompt_id"] == "weekly_goal_review"

    page = client.get("/prompts")
    assert page.status_code == 200
    assert "Prompt Registry" in page.text


def test_prompts_editor_load_and_save(tmp_path: Path) -> None:
    client, vault = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    _write(
        vault / "config/prompts/schemas/weekly_goal_review.json",
        '{"type":"object","properties":{"title":{"type":"string"}}}',
    )
    _write(
        vault / "config/prompts/weekly_goal_review.yaml",
        """id: weekly_goal_review
version: v1
provider: openai
model: gpt-5.2
params:
  temperature: 0.1
schema: schemas/weekly_goal_review.json
system: |
  You are a review assistant.
user: |
  Summarize this week.
""",
    )
    assert client.post("/api/prompts/reload").status_code == 200

    editor = client.get("/api/prompts/editor")
    assert editor.status_code == 200
    files = editor.json()["files"]
    assert any(item["file"] == "weekly_goal_review.yaml" for item in files)

    updated_content = """id: weekly_goal_review
version: v1
provider: openai
model: gpt-5-mini
params:
  verbosity: low
schema: schemas/weekly_goal_review.json
system: |
  Updated review assistant.
user: |
  Summarize this week with concise output.
"""
    saved = client.post(
        "/api/prompts/editor",
        json={"file": "weekly_goal_review.yaml", "content": updated_content},
    )
    assert saved.status_code == 200
    saved_payload = saved.json()
    assert saved_payload["ok"] is True

    listed = client.get("/api/prompts")
    assert listed.status_code == 200
    items = listed.json()["items"]
    target = next(item for item in items if item["prompt_id"] == "weekly_goal_review")
    assert target["model"] == "gpt-5-mini"
