from __future__ import annotations

import hashlib
import json
from typing import Any


CONTENT_HASH_VERSION = "sha256-v1"
PAYLOAD_HASH_VERSION = "sha256-v1"

VOLATILE_PAYLOAD_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "version_no",
    "is_current",
    "supersedes_id",
    "source_run_id",
}


def _normalize_text_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_hash_from_text(text: str) -> str:
    normalized = _normalize_text_line_endings(text).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {
            key: _canonicalize(val)
            for key, val in value.items()
            if key not in VOLATILE_PAYLOAD_FIELDS
        }
        return {key: cleaned[key] for key in sorted(cleaned.keys())}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, str):
        return value.strip()
    return value


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    canonical = _canonicalize(payload)
    serialized = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

