from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.db.migrations import apply_sql_migrations
from app.services.search import search_entries


DEFAULT_QUERIES = [
    "sleep",
    "workout",
    "focus",
    "project",
    "goal",
    "review",
    "ideas",
    "food",
    "journal",
    "chat",
]


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = int(round((len(sorted_values) - 1) * p))
    return sorted_values[idx]


def _summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    sorted_values = sorted(values)
    return {
        "count": float(len(values)),
        "p50_ms": float(statistics.median(values)),
        "p95_ms": float(_percentile(sorted_values, 0.95)),
        "max_ms": float(max(values)),
    }


def _run_query(settings: Settings, q: str, page_size: int = 20) -> float:
    start = time.perf_counter()
    search_entries(settings, q=q, page=1, page_size=page_size)
    end = time.perf_counter()
    return (end - start) * 1000.0


def _load_queries(queries_csv: str, query_file: str | None) -> list[str]:
    if query_file:
        path = Path(query_file)
        lines = path.read_text(encoding="utf-8").splitlines()
        queries = []
        for line in lines:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            queries.append(value)
        return queries
    return [part.strip() for part in queries_csv.split(",") if part.strip()]


def _system_info(storage_label: str | None = None) -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or "unknown",
        "cpu_cores": os.cpu_count() or 0,
        "storage": storage_label or "unknown",
    }


def run_benchmark(
    settings: Settings,
    *,
    queries: list[str],
    runs_per_query: int = 20,
    page_size: int = 20,
    storage_label: str | None = None,
) -> dict[str, Any]:
    if not queries:
        raise ValueError("No queries provided.")

    apply_sql_migrations(Path.cwd(), settings)

    cold_ms: list[float] = []
    warm_ms: list[float] = []
    by_query: list[dict[str, Any]] = []

    for q in queries:
        cold = _run_query(settings, q, page_size=page_size)
        cold_ms.append(cold)
        warm_for_query: list[float] = []
        for _ in range(max(1, int(runs_per_query))):
            value = _run_query(settings, q, page_size=page_size)
            warm_ms.append(value)
            warm_for_query.append(value)
        by_query.append(
            {
                "query": q,
                "cold_ms": cold,
                "warm_ms": warm_for_query,
                "warm_summary": _summarize(warm_for_query),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "query_count": len(queries),
        "runs_per_query": int(runs_per_query),
        "system": _system_info(storage_label=storage_label),
        "cold": {
            "latencies_ms": cold_ms,
            "summary": _summarize(cold_ms),
        },
        "warm": {
            "latencies_ms": warm_ms,
            "summary": _summarize(warm_ms),
        },
        "by_query": by_query,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark FTS search latency.")
    parser.add_argument("--db", required=True, help="Path to sqlite db")
    parser.add_argument("--vault", required=True, help="Path to vault root")
    parser.add_argument("--timezone", default="UTC")
    parser.add_argument("--runs", type=int, default=20, help="Warm runs per query")
    parser.add_argument("--page-size", type=int, default=20, help="Result page size per query")
    parser.add_argument("--storage-label", default="unknown", help="Storage type label for report")
    parser.add_argument(
        "--queries",
        default=",".join(DEFAULT_QUERIES),
        help="Comma-separated query list",
    )
    parser.add_argument("--query-file", default=None, help="File with one query per line")
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to write full benchmark report as JSON",
    )
    args = parser.parse_args()

    queries = _load_queries(args.queries, args.query_file)
    if not queries:
        print("No queries provided.")
        return 2

    settings = Settings(
        LIFEOS_DB_PATH=str(Path(args.db)),
        LIFEOS_VAULT_PATH=str(Path(args.vault)),
        LIFEOS_TIMEZONE=args.timezone,
    )
    report = run_benchmark(
        settings,
        queries=queries,
        runs_per_query=args.runs,
        page_size=args.page_size,
        storage_label=args.storage_label,
    )

    cold_summary = report["cold"]["summary"]
    warm_summary = report["warm"]["summary"]
    print("Search Benchmark")
    print(f"queries={report['query_count']} runs_per_query={report['runs_per_query']}")
    print(
        "cold_ms:"
        f" p50={cold_summary['p50_ms']:.2f}"
        f" p95={cold_summary['p95_ms']:.2f}"
        f" max={cold_summary['max_ms']:.2f}"
    )
    print(
        "warm_ms:"
        f" p50={warm_summary['p50_ms']:.2f}"
        f" p95={warm_summary['p95_ms']:.2f}"
        f" max={warm_summary['max_ms']:.2f}"
    )

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"report_json={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
