from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.engine import get_connection


@dataclass
class SearchResult:
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
    facets: dict[str, list[dict[str, Any]]]


def _base_filters(
    *,
    entry_type: str | None,
    tag: str | None,
    goal: str | None,
) -> tuple[str, list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    if entry_type:
        where.append("e.type = ?")
        params.append(entry_type)
    if tag:
        where.append(
            "EXISTS (SELECT 1 FROM json_each(e.tags_json) jt WHERE CAST(jt.value AS TEXT) = ?)"
        )
        params.append(tag)
    if goal:
        where.append(
            "EXISTS (SELECT 1 FROM json_each(e.goals_json) jg WHERE CAST(jg.value AS TEXT) = ?)"
        )
        params.append(goal)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return where_sql, params


def search_entries(
    settings,
    *,
    q: str,
    entry_type: str | None = None,
    tag: str | None = None,
    goal: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> SearchResult:
    query = (q or "").strip()
    if not query:
        raise ValueError("Search query cannot be empty.")

    where_sql, where_params = _base_filters(entry_type=entry_type, tag=tag, goal=goal)
    offset = (page - 1) * page_size

    conn = get_connection(settings)
    try:
        total = conn.execute(
            f"""
            WITH matched AS (
              SELECT m.entry_id
              FROM fts_entries f
              JOIN fts_entries_map m ON m.fts_rowid = f.rowid
              WHERE fts_entries MATCH ?
            )
            SELECT COUNT(*) AS c
            FROM matched
            JOIN entries_index e ON e.id = matched.entry_id
            {where_sql}
            """,
            (query, *where_params),
        ).fetchone()["c"]

        rows = conn.execute(
            f"""
            WITH matched AS (
              SELECT
                m.entry_id,
                bm25(fts_entries) AS score,
                snippet(fts_entries, 0, '[', ']', ' ... ', 8) AS summary_snippet,
                snippet(fts_entries, 1, '[', ']', ' ... ', 16) AS raw_snippet
              FROM fts_entries
              JOIN fts_entries_map m ON m.fts_rowid = fts_entries.rowid
              WHERE fts_entries MATCH ?
            )
            SELECT
              e.id,
              e.path,
              e.created_at,
              e.type,
              e.status,
              e.summary,
              e.tags_json,
              e.goals_json,
              matched.score,
              matched.summary_snippet,
              matched.raw_snippet
            FROM matched
            JOIN entries_index e ON e.id = matched.entry_id
            {where_sql}
            ORDER BY matched.score ASC, e.created_at DESC, e.id DESC
            LIMIT ? OFFSET ?
            """,
            (query, *where_params, int(page_size), int(offset)),
        ).fetchall()

        type_facets = conn.execute(
            f"""
            WITH matched AS (
              SELECT m.entry_id
              FROM fts_entries
              JOIN fts_entries_map m ON m.fts_rowid = fts_entries.rowid
              WHERE fts_entries MATCH ?
            )
            SELECT e.type AS value, COUNT(*) AS count
            FROM matched
            JOIN entries_index e ON e.id = matched.entry_id
            {where_sql}
            GROUP BY e.type
            ORDER BY count DESC, value ASC
            """,
            (query, *where_params),
        ).fetchall()

        tag_facets = conn.execute(
            f"""
            WITH matched AS (
              SELECT m.entry_id
              FROM fts_entries
              JOIN fts_entries_map m ON m.fts_rowid = fts_entries.rowid
              WHERE fts_entries MATCH ?
            )
            SELECT CAST(jt.value AS TEXT) AS value, COUNT(*) AS count
            FROM matched
            JOIN entries_index e ON e.id = matched.entry_id
            JOIN json_each(e.tags_json) jt
            {where_sql}
            GROUP BY CAST(jt.value AS TEXT)
            ORDER BY count DESC, value ASC
            """,
            (query, *where_params),
        ).fetchall()

        goal_facets = conn.execute(
            f"""
            WITH matched AS (
              SELECT m.entry_id
              FROM fts_entries
              JOIN fts_entries_map m ON m.fts_rowid = fts_entries.rowid
              WHERE fts_entries MATCH ?
            )
            SELECT CAST(jg.value AS TEXT) AS value, COUNT(*) AS count
            FROM matched
            JOIN entries_index e ON e.id = matched.entry_id
            JOIN json_each(e.goals_json) jg
            {where_sql}
            GROUP BY CAST(jg.value AS TEXT)
            ORDER BY count DESC, value ASC
            """,
            (query, *where_params),
        ).fetchall()
    finally:
        conn.close()

    total_pages = max(1, (int(total) + page_size - 1) // page_size)
    items = [
        {
            "id": row["id"],
            "path": row["path"],
            "created_at": row["created_at"],
            "type": row["type"],
            "status": row["status"],
            "summary": row["summary"] or "",
            "summary_snippet": row["summary_snippet"] or row["summary"] or "",
            "raw_snippet": row["raw_snippet"] or "",
            "score": float(row["score"] if row["score"] is not None else 0.0),
        }
        for row in rows
    ]
    facets = {
        "type": [{"value": row["value"], "count": int(row["count"])} for row in type_facets],
        "tags": [{"value": row["value"], "count": int(row["count"])} for row in tag_facets],
        "goals": [{"value": row["value"], "count": int(row["count"])} for row in goal_facets],
    }
    return SearchResult(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        facets=facets,
    )
