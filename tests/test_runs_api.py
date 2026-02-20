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


def test_runs_api_log_list_detail_and_page(tmp_path: Path) -> None:
    client, vault = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    _write(
        vault / "config/prompts/schemas/distill_outcomes.json",
        '{"type":"object","properties":{"summary":{"type":"string"}},"required":["summary"]}',
    )
    _write(
        vault / "config/prompts/distill_outcomes.yaml",
        """id: distill_outcomes
version: v1
provider: openai
model: gpt-5-mini
params:
  temperature: 0.1
schema: schemas/distill_outcomes.json
system: |
  Distill outcomes from text.
user: |
  {{raw_text}}
""",
    )
    reload_resp = client.post("/api/prompts/reload")
    assert reload_resp.status_code == 200
    assert reload_resp.json()["loaded"] == 1

    success_log = client.post(
        "/api/runs/log",
        json={
            "prompt_id": "distill_outcomes",
            "prompt_version": "v1",
            "model": "gpt-5-mini",
            "status": "success",
            "input_refs": ["entry-1"],
            "output": {"summary": "ok"},
            "parse_ok": True,
        },
    )
    assert success_log.status_code == 200
    success_run = success_log.json()["run_id"]

    failed_log = client.post(
        "/api/runs/log",
        json={
            "prompt_id": "distill_outcomes",
            "prompt_version": "v1",
            "model": "gpt-5-mini",
            "status": "failed",
            "input_refs": ["entry-2"],
            "output": {"raw": "bad"},
            "parse_ok": False,
            "error_text": "schema validation failed",
        },
    )
    assert failed_log.status_code == 200
    failed_run = failed_log.json()["run_id"]

    # Even if caller asks for success, schema validation should fail and persist as failed.
    schema_failed_log = client.post(
        "/api/runs/log",
        json={
            "prompt_id": "distill_outcomes",
            "prompt_version": "v1",
            "model": "gpt-5-mini",
            "status": "success",
            "input_refs": ["entry-3"],
            "output": {"wrong_key": "no summary"},
            "validate_schema": True,
        },
    )
    assert schema_failed_log.status_code == 200
    schema_failed_payload = schema_failed_log.json()
    assert schema_failed_payload["status"] == "failed"
    assert schema_failed_payload["parse_ok"] is False
    assert "schema:" in (schema_failed_payload["error_text"] or "")

    listed = client.get("/api/runs")
    assert listed.status_code == 200
    assert listed.json()["total"] == 3

    failed_only = client.get("/api/runs", params={"status": "failed"})
    assert failed_only.status_code == 200
    assert failed_only.json()["total"] == 2
    failed_ids = {item["run_id"] for item in failed_only.json()["items"]}
    assert failed_run in failed_ids
    assert schema_failed_payload["run_id"] in failed_ids

    detail = client.get(f"/api/runs/{success_run}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["status"] == "success"
    assert detail_payload["parse_ok"] is True
    assert detail_payload["output"]["summary"] == "ok"
    assert detail_payload["parent_run_id"] is None

    retry = client.post(f"/api/runs/{failed_run}/retry", json={"actor": "local_user"})
    assert retry.status_code == 200
    retry_payload = retry.json()
    assert retry_payload["parent_run_id"] == failed_run
    assert retry_payload["status"] == "failed"
    assert retry_payload["parse_ok"] is False

    page = client.get("/runs")
    assert page.status_code == 200
    assert "Prompt Runs" in page.text
