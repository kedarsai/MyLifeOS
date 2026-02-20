from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.search import search_entries
from app.tools.generate_search_fixture import generate_search_fixture


def test_generate_search_fixture_populates_entries_and_fts(tmp_path: Path) -> None:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )

    out = generate_search_fixture(
        settings,
        count=120,
        seed=9,
        prefix="bench",
        clear_existing_prefix=True,
    )
    assert out["inserted_or_updated"] == 120
    assert out["total_entries"] >= 120
    assert out["total_fts_rows"] == out["total_entries"]

    result = search_entries(settings, q="zenith", page=1, page_size=10)
    assert result.total > 0
    assert len(result.items) <= 10
