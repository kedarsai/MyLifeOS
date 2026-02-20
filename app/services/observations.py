from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from app.core.hashing import PAYLOAD_HASH_VERSION, canonical_payload_hash
from app.core.time import utc_now_iso
from app.db.engine import get_connection


_STEPS_RE = re.compile(r"\b(\d{3,7})\s*steps?\b", re.IGNORECASE)
_DURATION_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:min|mins|minutes)\b", re.IGNORECASE)
_DIST_KM_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*km\b", re.IGNORECASE)
_DIST_MI_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:mi|mile|miles)\b", re.IGNORECASE)
_CAL_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:kcal|calories?|cals?)\b", re.IGNORECASE)
_SLEEP_HOURS_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b", re.IGNORECASE)
_SLEEP_MIN_RE = re.compile(r"\b(\d{1,3})\s*(?:m|min|mins|minute|minutes)\b", re.IGNORECASE)
_SLEEP_QUALITY_RE = re.compile(
    r"(?:\bquality\b|\bscore\b)\s*[:=]?\s*([1-5])\b|\b([1-5])\s*/\s*5\b",
    re.IGNORECASE,
)
_WEIGHT_RE = re.compile(
    r"\b(\d{2,3}(?:\.\d+)?)\s*(kg|kgs|kilogram|kilograms|lb|lbs|pound|pounds)\b",
    re.IGNORECASE,
)


@dataclass
class ActivityObservation:
    steps: int | None
    duration_min: float | None
    distance_km: float | None
    calories: float | None
    notes: str


@dataclass
class SleepObservation:
    duration_min: float | None
    quality: int | None
    notes: str


@dataclass
class FoodObservation:
    meal_type: str
    items: list[str]
    notes: str


@dataclass
class WeightObservation:
    weight_kg: float
    notes: str


def _to_float(match: re.Match | None) -> float | None:
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def extract_activity_observation(*, entry_type: str, raw_text: str) -> ActivityObservation | None:
    text = raw_text or ""
    lower = text.lower()
    looks_activity = entry_type == "activity" or any(
        token in lower for token in ("steps", "workout", "exercise", "run", "walk", "gym", "km", "mile")
    )
    if not looks_activity:
        return None

    steps_match = _STEPS_RE.search(text)
    duration_match = _DURATION_RE.search(text)
    km_match = _DIST_KM_RE.search(text)
    mi_match = _DIST_MI_RE.search(text)
    cal_match = _CAL_RE.search(text)

    steps = int(steps_match.group(1)) if steps_match else None
    duration_min = _to_float(duration_match)
    distance_km = _to_float(km_match)
    if distance_km is None and mi_match:
        miles = _to_float(mi_match)
        distance_km = round((miles or 0.0) * 1.60934, 3) if miles is not None else None
    calories = _to_float(cal_match)

    if steps is None and duration_min is None and distance_km is None and calories is None and entry_type != "activity":
        return None

    notes = " ".join(text.strip().split())[:240]
    return ActivityObservation(
        steps=steps,
        duration_min=duration_min,
        distance_km=distance_km,
        calories=calories,
        notes=notes or "",
    )


def extract_sleep_observation(*, entry_type: str, raw_text: str) -> SleepObservation | None:
    text = raw_text or ""
    lower = text.lower()
    looks_sleep = entry_type == "sleep" or any(token in lower for token in ("sleep", "slept", "nap", "bed"))
    if not looks_sleep:
        return None

    hours = _to_float(_SLEEP_HOURS_RE.search(text))
    minutes_match = _SLEEP_MIN_RE.search(text)
    minutes = float(minutes_match.group(1)) if minutes_match else 0.0
    duration_min = None
    if hours is not None:
        duration_min = round(hours * 60.0 + minutes, 2)
    elif minutes_match:
        duration_min = minutes

    quality_match = _SLEEP_QUALITY_RE.search(text)
    quality_raw = quality_match.group(1) if quality_match and quality_match.group(1) else (quality_match.group(2) if quality_match else None)
    quality = int(quality_raw) if quality_raw else None

    if duration_min is None and quality is None and entry_type != "sleep":
        return None

    notes = " ".join(text.strip().split())[:240]
    return SleepObservation(duration_min=duration_min, quality=quality, notes=notes or "")


def extract_food_observation(*, entry_type: str, raw_text: str) -> FoodObservation | None:
    text = raw_text or ""
    lower = text.lower()
    looks_food = entry_type == "food" or any(
        token in lower for token in ("breakfast", "lunch", "dinner", "snack", "meal", "ate", "food")
    )
    if not looks_food:
        return None

    meal_type = "other"
    for candidate in ("breakfast", "lunch", "dinner", "snack"):
        if candidate in lower:
            meal_type = candidate
            break

    parts = re.split(r"[,\n;]+", text)
    items = []
    for part in parts:
        clean = " ".join(part.strip().split())
        if not clean:
            continue
        if len(clean) > 80:
            clean = clean[:80].rstrip() + "..."
        items.append(clean)
        if len(items) >= 12:
            break
    if not items:
        items = ["meal logged"]

    notes = " ".join(text.strip().split())[:240]
    return FoodObservation(meal_type=meal_type, items=items, notes=notes or "")


def extract_weight_observation(*, entry_type: str, raw_text: str) -> WeightObservation | None:
    text = raw_text or ""
    lower = text.lower()
    match = _WEIGHT_RE.search(text)
    if not match:
        return None

    if "weight" not in lower and "weigh" not in lower and entry_type not in {"goal", "note"}:
        return None

    value = float(match.group(1))
    unit = match.group(2).lower()
    weight_kg = value
    if unit in {"lb", "lbs", "pound", "pounds"}:
        weight_kg = round(value * 0.45359237, 3)
    if weight_kg <= 0:
        return None

    notes = " ".join(text.strip().split())[:240]
    return WeightObservation(weight_kg=weight_kg, notes=notes or "")


def upsert_activity_observation(
    settings,
    *,
    entry_id: str,
    source_run_id: str,
    entry_type: str,
    raw_text: str,
    observed_at: str | None = None,
) -> bool:
    extracted = extract_activity_observation(entry_type=entry_type, raw_text=raw_text)
    if not extracted:
        return False

    now = utc_now_iso()
    logical_id = f"obs-activity-{entry_id}"
    payload_seed = {
        "entry_id": entry_id,
        "logical_id": logical_id,
        "observed_at": observed_at,
        "steps": extracted.steps,
        "duration_min": extracted.duration_min,
        "distance_km": extracted.distance_km,
        "calories": extracted.calories,
        "notes": extracted.notes,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        latest = conn.execute(
            """
            SELECT observation_id, version_no
            FROM obs_activity
            WHERE logical_id = ? AND is_current = 1
            ORDER BY version_no DESC
            LIMIT 1
            """,
            (logical_id,),
        ).fetchone()
        supersedes_id = latest["observation_id"] if latest else None
        version_no = int(latest["version_no"]) + 1 if latest else 1

        if latest:
            conn.execute(
                "UPDATE obs_activity SET is_current = 0 WHERE logical_id = ?",
                (logical_id,),
            )

        observation_id = f"obs-activity-{uuid.uuid4()}"
        conn.execute(
            """
            INSERT INTO obs_activity (
              observation_id, logical_id, entry_id, source_run_id, observed_at,
              steps, duration_min, distance_km, calories, pace, location, notes,
              payload_hash, payload_hash_version, version_no, is_current, supersedes_id,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                observation_id,
                logical_id,
                entry_id,
                source_run_id,
                observed_at,
                extracted.steps,
                extracted.duration_min,
                extracted.distance_km,
                extracted.calories,
                extracted.notes,
                payload_hash,
                PAYLOAD_HASH_VERSION,
                version_no,
                supersedes_id,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def upsert_sleep_observation(
    settings,
    *,
    entry_id: str,
    source_run_id: str,
    entry_type: str,
    raw_text: str,
) -> bool:
    extracted = extract_sleep_observation(entry_type=entry_type, raw_text=raw_text)
    if not extracted:
        return False

    now = utc_now_iso()
    logical_id = f"obs-sleep-{entry_id}"
    payload_seed = {
        "entry_id": entry_id,
        "logical_id": logical_id,
        "sleep_start": None,
        "sleep_end": None,
        "duration_min": extracted.duration_min,
        "quality": extracted.quality,
        "notes": extracted.notes,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        latest = conn.execute(
            """
            SELECT observation_id, version_no
            FROM obs_sleep
            WHERE logical_id = ? AND is_current = 1
            ORDER BY version_no DESC
            LIMIT 1
            """,
            (logical_id,),
        ).fetchone()
        supersedes_id = latest["observation_id"] if latest else None
        version_no = int(latest["version_no"]) + 1 if latest else 1
        if latest:
            conn.execute("UPDATE obs_sleep SET is_current = 0 WHERE logical_id = ?", (logical_id,))

        observation_id = f"obs-sleep-{uuid.uuid4()}"
        conn.execute(
            """
            INSERT INTO obs_sleep (
              observation_id, logical_id, entry_id, source_run_id, sleep_start, sleep_end,
              duration_min, quality, notes, payload_hash, payload_hash_version, version_no,
              is_current, supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                observation_id,
                logical_id,
                entry_id,
                source_run_id,
                extracted.duration_min,
                extracted.quality,
                extracted.notes,
                payload_hash,
                PAYLOAD_HASH_VERSION,
                version_no,
                supersedes_id,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def upsert_food_observation(
    settings,
    *,
    entry_id: str,
    source_run_id: str,
    entry_type: str,
    raw_text: str,
) -> bool:
    extracted = extract_food_observation(entry_type=entry_type, raw_text=raw_text)
    if not extracted:
        return False

    now = utc_now_iso()
    logical_id = f"obs-food-{entry_id}"
    payload_seed = {
        "entry_id": entry_id,
        "logical_id": logical_id,
        "meal_type": extracted.meal_type,
        "items": extracted.items,
        "notes": extracted.notes,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        latest = conn.execute(
            """
            SELECT observation_id, version_no
            FROM obs_food
            WHERE logical_id = ? AND is_current = 1
            ORDER BY version_no DESC
            LIMIT 1
            """,
            (logical_id,),
        ).fetchone()
        supersedes_id = latest["observation_id"] if latest else None
        version_no = int(latest["version_no"]) + 1 if latest else 1
        if latest:
            conn.execute("UPDATE obs_food SET is_current = 0 WHERE logical_id = ?", (logical_id,))

        observation_id = f"obs-food-{uuid.uuid4()}"
        conn.execute(
            """
            INSERT INTO obs_food (
              observation_id, logical_id, entry_id, source_run_id, meal_type, items_json,
              notes, payload_hash, payload_hash_version, version_no, is_current,
              supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                observation_id,
                logical_id,
                entry_id,
                source_run_id,
                extracted.meal_type,
                json.dumps(extracted.items, separators=(",", ":"), ensure_ascii=True),
                extracted.notes,
                payload_hash,
                PAYLOAD_HASH_VERSION,
                version_no,
                supersedes_id,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def upsert_weight_observation(
    settings,
    *,
    entry_id: str,
    source_run_id: str,
    entry_type: str,
    raw_text: str,
    measured_at: str | None = None,
) -> bool:
    extracted = extract_weight_observation(entry_type=entry_type, raw_text=raw_text)
    if not extracted:
        return False

    now = utc_now_iso()
    logical_id = f"obs-weight-{entry_id}"
    payload_seed = {
        "entry_id": entry_id,
        "logical_id": logical_id,
        "measured_at": measured_at,
        "weight_kg": extracted.weight_kg,
        "notes": extracted.notes,
    }
    payload_hash = canonical_payload_hash(payload_seed)

    conn = get_connection(settings)
    try:
        latest = conn.execute(
            """
            SELECT observation_id, version_no
            FROM obs_weight
            WHERE logical_id = ? AND is_current = 1
            ORDER BY version_no DESC
            LIMIT 1
            """,
            (logical_id,),
        ).fetchone()
        supersedes_id = latest["observation_id"] if latest else None
        version_no = int(latest["version_no"]) + 1 if latest else 1
        if latest:
            conn.execute("UPDATE obs_weight SET is_current = 0 WHERE logical_id = ?", (logical_id,))

        observation_id = f"obs-weight-{uuid.uuid4()}"
        conn.execute(
            """
            INSERT INTO obs_weight (
              observation_id, logical_id, entry_id, source_run_id, measured_at, weight_kg,
              payload_hash, payload_hash_version, version_no, is_current, supersedes_id,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                observation_id,
                logical_id,
                entry_id,
                source_run_id,
                measured_at,
                extracted.weight_kg,
                payload_hash,
                PAYLOAD_HASH_VERSION,
                version_no,
                supersedes_id,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return True
