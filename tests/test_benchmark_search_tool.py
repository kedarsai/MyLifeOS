from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.tools.benchmark_search import run_benchmark
from app.tools.generate_search_fixture import generate_search_fixture


def test_run_benchmark_returns_report_shape(tmp_path: Path) -> None:
    settings = Settings(
        LIFEOS_VAULT_PATH=str(tmp_path / "Vault"),
        LIFEOS_DB_PATH=str(tmp_path / "data" / "lifeos.db"),
        LIFEOS_TIMEZONE="UTC",
    )
    generate_search_fixture(
        settings,
        count=80,
        seed=3,
        prefix="bench",
        clear_existing_prefix=True,
    )
    report = run_benchmark(
        settings,
        queries=["zenith", "focus", "project"],
        runs_per_query=2,
        page_size=10,
        storage_label="ssd",
    )
    assert report["query_count"] == 3
    assert report["runs_per_query"] == 2
    assert report["system"]["storage"] == "ssd"
    assert len(report["cold"]["latencies_ms"]) == 3
    assert len(report["warm"]["latencies_ms"]) == 6
    assert report["cold"]["summary"]["p95_ms"] >= 0
    assert len(report["by_query"]) == 3
