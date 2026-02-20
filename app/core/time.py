from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_datetime_iso(value: str, tz_name: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    try:
        target_tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        target_tz = timezone.utc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=target_tz)
    return dt.astimezone(target_tz).replace(microsecond=0).isoformat()
