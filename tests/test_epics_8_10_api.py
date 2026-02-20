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


def test_chat_reminders_and_reviews_flow(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.post("/api/admin/migrate").status_code == 200

    goal = client.post(
        "/api/goals",
        json={
            "name": "Weekly consistency",
            "start_date": "2026-02-19",
            "metrics": ["steps", "sleep", "food"],
            "status": "active",
            "review_cadence_days": 7,
        },
    )
    assert goal.status_code == 200
    goal_id = goal.json()["goal_id"]

    captured = client.post(
        "/api/entries/capture",
        json={
            "raw_text": "Evening walk 6200 steps in 42 minutes. TODO: stretch due:2026-02-20.",
            "type": "activity",
            "goals": [goal_id],
        },
    )
    assert captured.status_code == 200
    entry_id = captured.json()["entry_id"]
    assert client.post(f"/api/goals/{goal_id}/link-entry", json={"entry_id": entry_id}).status_code == 200
    assert client.post("/api/entries/process-inbox", json={"entry_ids": [entry_id], "limit": 5}).status_code == 200

    # Form-encoded thread creation/message add should work for HTMX UI flows.
    thread_html = client.post(
        "/api/chat/threads?format=html",
        data={"title": "Goal coaching session", "goal_id": goal_id},
    )
    assert thread_html.status_code == 200
    threads = client.get("/api/chat/threads").json()["items"]
    assert threads
    thread_id = threads[0]["thread_id"]

    msg_html = client.post(
        f"/api/chat/threads/{thread_id}/messages?format=html",
        data={"role": "assistant", "content": "- Improve bedtime routine\n- Log food daily"},
    )
    assert msg_html.status_code == 200

    reply = client.post(f"/api/chat/threads/{thread_id}/reply")
    assert reply.status_code == 200
    assert reply.json()["assistant_message"]

    distilled = client.post(f"/api/chat/threads/{thread_id}/distill")
    assert distilled.status_code == 200
    assert distilled.json()["tasks_created_or_updated"] >= 1

    # Backfilled check-in should accept form data and process immediately.
    checkin = client.post(
        "/api/checkin/sleep",
        data={"date": "2026-02-18", "notes": "Slept 7 hours quality 4", "goal_id": goal_id},
    )
    assert checkin.status_code == 200
    c = checkin.json()
    assert c["processed_count"] == 1

    day_timeline = client.get(
        "/api/entries/timeline",
        params={"page": 1, "page_size": 100, "date_from": "2026-02-18", "date_to": "2026-02-18"},
    )
    assert day_timeline.status_code == 200
    assert any(item["id"] == c["entry_id"] for item in day_timeline.json()["items"])

    review = client.post("/api/reviews/generate", json={"goal_id": goal_id, "week_start": "2026-02-16"})
    assert review.status_code == 200
    r = review.json()
    assert r["goal_id"] == goal_id
    assert r["review"]["next_best_actions"]

    reviews_list = client.get("/api/reviews", params={"goal_id": goal_id})
    assert reviews_list.status_code == 200
    assert reviews_list.json()["total"] >= 1

    backup = client.post("/api/backups/run", data={"mode": "hourly"})
    assert backup.status_code == 200
    assert backup.json()["ok"] is True

    dashboard = client.get(f"/api/goals/{goal_id}/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["latest_review"] is not None

    assert client.get("/reviews").status_code == 200
