from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.db.engine import get_connection
from app.db.migrations import apply_sql_migrations
from app.services.observations import (
    extract_activity_observation,
    extract_food_observation,
    extract_sleep_observation,
    extract_weight_observation,
    upsert_activity_observation,
    upsert_food_observation,
    upsert_sleep_observation,
    upsert_weight_observation,
)


def test_extract_activity_observation_parses_metrics() -> None:
    raw = "Evening run: 4.2 km in 28 minutes, 410 calories, 6100 steps."
    obs = extract_activity_observation(entry_type="activity", raw_text=raw)
    assert obs is not None
    assert obs.steps == 6100
    assert obs.duration_min == 28.0
    assert obs.distance_km == 4.2
    assert obs.calories == 410.0


def test_upsert_activity_observation_versions_chain(tmp_path: Path) -> None:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    apply_sql_migrations(Path.cwd(), settings)

    conn = get_connection(settings)
    try:
        conn.execute(
            """
            INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json, created_at)
            VALUES ('manual-seed', 'manual', 'test', '{}', '2026-02-19T10:00:00+00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO entries_index (
              id, path, created_at, updated_at, captured_tz, type, status, summary,
              raw_text, details_md, actions_md, tags_json, goals_json, source_run_id,
              content_hash, content_hash_version
            )
            VALUES (
              'entry-obs-1', 'Vault/entries/entry-obs-1.md',
              '2026-02-19T10:00:00+00:00', '2026-02-19T10:00:00+00:00',
              'UTC', 'activity', 'processed', 'obs',
              'raw', '', '', ?, ?, 'manual-seed', 'hash-entry', 'sha256-v1'
            )
            """,
            (json.dumps(["fitness"]), json.dumps([])),
        )
        conn.commit()
    finally:
        conn.close()

    assert upsert_activity_observation(
        settings,
        entry_id="entry-obs-1",
        source_run_id="manual-seed",
        entry_type="activity",
        raw_text="Walked 4000 steps in 20 minutes.",
        observed_at="2026-02-19T10:00:00+00:00",
    )
    assert upsert_activity_observation(
        settings,
        entry_id="entry-obs-1",
        source_run_id="manual-seed",
        entry_type="activity",
        raw_text="Walked 5000 steps in 25 minutes.",
        observed_at="2026-02-19T11:00:00+00:00",
    )

    conn = get_connection(settings)
    try:
        rows = conn.execute(
            """
            SELECT version_no, steps, is_current
            FROM obs_activity
            WHERE entry_id = 'entry-obs-1'
            ORDER BY version_no ASC
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    assert int(rows[0]["version_no"]) == 1
    assert int(rows[0]["steps"]) == 4000
    assert int(rows[0]["is_current"]) == 0
    assert int(rows[1]["version_no"]) == 2
    assert int(rows[1]["steps"]) == 5000
    assert int(rows[1]["is_current"]) == 1


def test_extract_sleep_food_weight_observations() -> None:
    sleep = extract_sleep_observation(entry_type="sleep", raw_text="Slept 7.5 hours, quality 4.")
    assert sleep is not None
    assert sleep.duration_min == 450.0
    assert sleep.quality == 4

    food = extract_food_observation(entry_type="food", raw_text="Lunch: rice bowl, yogurt, banana.")
    assert food is not None
    assert food.meal_type == "lunch"
    assert len(food.items) >= 2

    weight = extract_weight_observation(entry_type="note", raw_text="Morning weight 180 lb after workout.")
    assert weight is not None
    assert abs(weight.weight_kg - 81.647) < 0.01


def test_upsert_sleep_food_weight(tmp_path: Path) -> None:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    apply_sql_migrations(Path.cwd(), settings)

    conn = get_connection(settings)
    try:
        conn.execute(
            """
            INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json, created_at)
            VALUES ('manual-seed', 'manual', 'test', '{}', '2026-02-19T10:00:00+00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO entries_index (
              id, path, created_at, updated_at, captured_tz, type, status, summary,
              raw_text, details_md, actions_md, tags_json, goals_json, source_run_id,
              content_hash, content_hash_version
            )
            VALUES (
              'entry-obs-2', 'Vault/entries/entry-obs-2.md',
              '2026-02-19T10:00:00+00:00', '2026-02-19T10:00:00+00:00',
              'UTC', 'note', 'processed', 'obs2',
              'raw', '', '', ?, ?, 'manual-seed', 'hash-entry-2', 'sha256-v1'
            )
            """,
            (json.dumps(["health"]), json.dumps([])),
        )
        conn.commit()
    finally:
        conn.close()

    assert upsert_sleep_observation(
        settings,
        entry_id="entry-obs-2",
        source_run_id="manual-seed",
        entry_type="sleep",
        raw_text="Slept 8 hours quality 5.",
    )
    assert upsert_food_observation(
        settings,
        entry_id="entry-obs-2",
        source_run_id="manual-seed",
        entry_type="food",
        raw_text="Dinner: lentils, salad.",
    )
    assert upsert_weight_observation(
        settings,
        entry_id="entry-obs-2",
        source_run_id="manual-seed",
        entry_type="note",
        raw_text="Weight 79.2 kg this morning.",
        measured_at="2026-02-19T08:00:00+00:00",
    )

    conn = get_connection(settings)
    try:
        sleep_rows = conn.execute("SELECT COUNT(*) AS c FROM obs_sleep WHERE entry_id = 'entry-obs-2'").fetchone()
        food_rows = conn.execute("SELECT COUNT(*) AS c FROM obs_food WHERE entry_id = 'entry-obs-2'").fetchone()
        weight_rows = conn.execute("SELECT COUNT(*) AS c FROM obs_weight WHERE entry_id = 'entry-obs-2'").fetchone()
    finally:
        conn.close()

    assert int(sleep_rows["c"]) == 1
    assert int(food_rows["c"]) == 1
    assert int(weight_rows["c"]) == 1
