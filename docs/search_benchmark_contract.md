# Search Benchmark Contract

Last updated: 2026-02-19

## Scope

This benchmark measures Epic 3 search latency for FTS-backed queries exposed by `GET /api/search`.

## Fixture Baseline

- Dataset size target: `50,000` entries in `entries_index` + `fts_entries`
- Minimum useful smoke fixture: `5,000` entries
- Distribution guidance:
  - entry types: realistic mix across `note`, `idea`, `todo`, `activity`, `chat`
  - tags: average `2-4` tags per entry
  - goals: average `0-2` goals per entry
  - body text length: varied (`50-600` chars)

## Query Set

Use a stable query corpus with at least:

- `10` single-term searches (for example: `sleep`, `workout`, `focus`)
- `10` multi-term searches (for example: `morning routine`, `project review`)
- `5` low-selectivity terms (common words)
- `5` high-selectivity terms (rare words)
- `5` filtered queries using facets (`type`, `tag`, `goal`)

Reference corpus file in repo:

- `docs/benchmark_queries.txt`

## Hardware Baseline

Record each run with:

- CPU model and core count
- RAM
- Storage type (SSD/HDD)
- OS version
- Python version

## Measurement Method

- Cold run: first execution of each query after process start
- Warm run: repeated execution in same process
- Metrics: `p50`, `p95`, `max` latency in milliseconds

## Pass/Fail Contract

- For large vault baseline (`50k` entries), target:
  - warm `p95 < 1000 ms`
- Report includes:
  - query count
  - per-query latency list
  - aggregate cold/warm metrics

## Command

```bash
uv run python -m app.tools.generate_search_fixture --db data/lifeos.db --vault Vault --count 50000 --seed 42 --prefix bench --clear-prefix
uv run python -m app.tools.benchmark_search --db data/lifeos.db --vault Vault --storage-label "nvme-ssd" --query-file docs/benchmark_queries.txt --output-json reports/search_benchmark.json
```
