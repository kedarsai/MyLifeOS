from app.core.hashing import canonical_payload_hash


def test_canonical_payload_hash_ignores_volatile_fields() -> None:
    a = {
        "title": "Walk 8k",
        "priority": "high",
        "updated_at": "2026-01-01T00:00:00Z",
        "source_run_id": "run-a",
        "is_current": True,
    }
    b = {
        "priority": "high",
        "title": "Walk 8k",
        "updated_at": "2026-01-02T00:00:00Z",
        "source_run_id": "run-b",
        "is_current": False,
    }
    assert canonical_payload_hash(a) == canonical_payload_hash(b)

