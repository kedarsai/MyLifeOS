from __future__ import annotations

import difflib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.time import utc_now_iso
from app.db.engine import get_connection
from app.services.indexer import VaultIndexer
from app.vault.manager import VaultManager
from app.vault.markdown import parse_markdown_note, render_entry_note


RESOLUTION_MAP = {
    "keep_vault": "resolved_keep_vault",
    "keep_app": "resolved_keep_app",
    "merge": "resolved_merged",
}


@dataclass
class ConflictListResult:
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


def _json_load(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default
    return parsed


def _json_dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def count_open_conflicts(settings) -> int:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM sync_conflicts WHERE conflict_status = 'open'"
        ).fetchone()
    finally:
        conn.close()
    return int(row["c"])


def list_conflicts(
    settings,
    *,
    status: str = "open",
    entity_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ConflictListResult:
    where: list[str] = []
    params: list[Any] = []

    status = (status or "open").strip().lower()
    if status == "open":
        where.append("c.conflict_status = 'open'")
    elif status == "resolved":
        where.append("c.conflict_status != 'open'")
    elif status != "all":
        raise ValueError(f"Unsupported status filter: {status}")

    if entity_type:
        where.append("c.entity_type = ?")
        params.append(entity_type.strip().lower())
    if date_from:
        where.append("date(c.created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(c.created_at) <= date(?)")
        params.append(date_to)

    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    conn = get_connection(settings)
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM sync_conflicts c{where_sql}",
            tuple(params),
        ).fetchone()["c"]

        rows = conn.execute(
            f"""
            SELECT
              c.conflict_id,
              c.entity_type,
              c.entity_id,
              c.logical_id,
              c.path,
              c.app_run_id,
              c.conflict_status,
              c.details_json,
              c.created_at,
              c.resolved_at
            FROM sync_conflicts c
            {where_sql}
            ORDER BY c.created_at DESC, c.conflict_id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, int(limit), int(offset)),
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in rows:
        details = _json_load(row["details_json"], {})
        summary = str(details.get("summary") or "")
        items.append(
            {
                "conflict_id": row["conflict_id"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "logical_id": row["logical_id"],
                "path": row["path"],
                "app_run_id": row["app_run_id"],
                "conflict_status": row["conflict_status"],
                "summary": summary,
                "created_at": row["created_at"],
                "resolved_at": row["resolved_at"],
            }
        )

    return ConflictListResult(items=items, total=int(total), limit=int(limit), offset=int(offset))


def _db_entry_snapshot_or_none(conn, entity_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
          id, created_at, updated_at, type, status, summary, source_run_id,
          raw_text, details_md, actions_md, tags_json, goals_json
        FROM entries_index
        WHERE id = ?
        """,
        (entity_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "created": row["created_at"],
        "updated": row["updated_at"],
        "type": row["type"],
        "status": row["status"],
        "summary": row["summary"] or "",
        "source_run_id": row["source_run_id"],
        "raw_text": row["raw_text"] or "",
        "details_md": row["details_md"] or "",
        "actions_md": row["actions_md"] or "",
        "tags": _json_load(row["tags_json"], []),
        "goals": _json_load(row["goals_json"], []),
    }


def _vault_entry_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    parsed = parse_markdown_note(text)
    fm = parsed.frontmatter
    return {
        "id": fm.get("id"),
        "created": fm.get("created"),
        "updated": fm.get("updated"),
        "type": fm.get("type"),
        "status": fm.get("status"),
        "summary": fm.get("summary"),
        "source_run_id": fm.get("source_run_id"),
        "raw_text": parsed.sections.get("Context (Raw)", ""),
        "details_md": parsed.sections.get("Details", ""),
        "actions_md": parsed.sections.get("Actions", ""),
        "tags": fm.get("tags") if isinstance(fm.get("tags"), list) else [],
        "goals": fm.get("goals") if isinstance(fm.get("goals"), list) else [],
    }


def _snapshot_to_markdown(snapshot: dict[str, Any], fallback_run_id: str) -> str:
    frontmatter = {
        "id": str(snapshot.get("id") or ""),
        "created": str(snapshot.get("created") or utc_now_iso()),
        "updated": str(snapshot.get("updated") or utc_now_iso()),
        "type": str(snapshot.get("type") or "note"),
        "status": str(snapshot.get("status") or "inbox"),
        "goals": snapshot.get("goals") if isinstance(snapshot.get("goals"), list) else [],
        "tags": snapshot.get("tags") if isinstance(snapshot.get("tags"), list) else [],
        "summary": str(snapshot.get("summary") or "Conflict Resolution"),
        "source_run_id": str(snapshot.get("source_run_id") or fallback_run_id),
    }
    return render_entry_note(
        frontmatter=frontmatter,
        details=str(snapshot.get("details_md") or "-"),
        actions=str(snapshot.get("actions_md") or "-"),
        raw_text=str(snapshot.get("raw_text") or ""),
    )


def _text_or_empty(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _merge_text(vault_text: str, app_text: str) -> str:
    left = (vault_text or "").strip()
    right = (app_text or "").strip()
    if left and not right:
        return left
    if right and not left:
        return right
    if left == right:
        return left
    return f"{left}\n\n--- merged ---\n\n{right}".strip()


def _merge_lists(left: list[str], right: list[str]) -> list[str]:
    merged: list[str] = []
    for value in [*left, *right]:
        item = str(value).strip()
        if item and item not in merged:
            merged.append(item)
    return merged


def get_conflict(settings, conflict_id: str) -> dict[str, Any] | None:
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT
              conflict_id, entity_type, entity_id, logical_id, path, app_run_id,
              vault_content_hash, vault_hash_version, db_content_hash, db_hash_version,
              conflict_status, details_json, created_at, resolved_at
            FROM sync_conflicts
            WHERE conflict_id = ?
            """,
            (conflict_id,),
        ).fetchone()
        if not row:
            return None

        details = _json_load(row["details_json"], {})
        path = Path(str(row["path"]))
        vault_text = _text_or_empty(path)

        app_snapshot = _db_entry_snapshot_or_none(conn, str(row["entity_id"])) or {}
        override_snapshot = details.get("app_snapshot")
        if isinstance(override_snapshot, dict):
            app_snapshot.update(override_snapshot)

        app_text = str(details.get("app_text") or "")
        if not app_text and row["entity_type"] == "entry":
            app_text = _snapshot_to_markdown(app_snapshot, str(row["app_run_id"]))

        diff_text = "".join(
            difflib.unified_diff(
                vault_text.splitlines(keepends=True),
                app_text.splitlines(keepends=True),
                fromfile="vault",
                tofile="app",
            )
        )

        events = conn.execute(
            """
            SELECT event_id, action, actor, source_run_id, notes, created_at
            FROM sync_conflict_events
            WHERE conflict_id = ?
            ORDER BY created_at DESC, event_id DESC
            """,
            (conflict_id,),
        ).fetchall()
    finally:
        conn.close()

    return {
        "conflict_id": row["conflict_id"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "logical_id": row["logical_id"],
        "path": row["path"],
        "app_run_id": row["app_run_id"],
        "vault_content_hash": row["vault_content_hash"],
        "vault_hash_version": row["vault_hash_version"],
        "db_content_hash": row["db_content_hash"],
        "db_hash_version": row["db_hash_version"],
        "conflict_status": row["conflict_status"],
        "details": details,
        "created_at": row["created_at"],
        "resolved_at": row["resolved_at"],
        "vault_text": vault_text,
        "app_text": app_text,
        "diff_text": diff_text,
        "events": [
            {
                "event_id": e["event_id"],
                "action": e["action"],
                "actor": e["actor"],
                "source_run_id": e["source_run_id"],
                "notes": e["notes"],
                "created_at": e["created_at"],
            }
            for e in events
        ],
    }


def resolve_conflict(
    settings,
    *,
    conflict_id: str,
    action: str,
    actor: str = "local_user",
    notes: str | None = None,
) -> dict[str, Any]:
    resolved_status = RESOLUTION_MAP.get(action)
    if not resolved_status:
        raise ValueError(f"Unsupported resolve action: {action}")

    now = utc_now_iso()
    conn = get_connection(settings)
    try:
        row = conn.execute(
            """
            SELECT
              conflict_id, entity_type, entity_id, logical_id, path, app_run_id,
              vault_content_hash, db_content_hash, conflict_status, details_json
            FROM sync_conflicts
            WHERE conflict_id = ?
            """,
            (conflict_id,),
        ).fetchone()
        if not row:
            raise KeyError(f"Conflict not found: {conflict_id}")
        if row["conflict_status"] != "open":
            raise ValueError("Conflict is already resolved.")

        details = _json_load(row["details_json"], {})
        path = Path(str(row["path"]))
        manager = VaultManager(settings)
        manager.ensure_layout()

        if action == "keep_vault":
            if path.exists():
                VaultIndexer(settings).index_paths([path])
        else:
            app_snapshot = _db_entry_snapshot_or_none(conn, str(row["entity_id"])) or {}
            override_snapshot = details.get("app_snapshot")
            if isinstance(override_snapshot, dict):
                app_snapshot.update(override_snapshot)

            if row["entity_type"] == "entry":
                if action == "merge":
                    vault_snapshot = _vault_entry_snapshot(path)
                    merged_snapshot = {
                        "id": str(app_snapshot.get("id") or vault_snapshot.get("id") or row["entity_id"]),
                        "created": str(
                            app_snapshot.get("created")
                            or vault_snapshot.get("created")
                            or now
                        ),
                        "updated": now,
                        "type": str(app_snapshot.get("type") or vault_snapshot.get("type") or "note"),
                        "status": str(app_snapshot.get("status") or vault_snapshot.get("status") or "inbox"),
                        "summary": str(
                            app_snapshot.get("summary")
                            or vault_snapshot.get("summary")
                            or f"Merged conflict {conflict_id}"
                        ),
                        "source_run_id": str(app_snapshot.get("source_run_id") or row["app_run_id"]),
                        "raw_text": _merge_text(
                            str(vault_snapshot.get("raw_text") or ""),
                            str(app_snapshot.get("raw_text") or ""),
                        ),
                        "details_md": _merge_text(
                            str(vault_snapshot.get("details_md") or ""),
                            str(app_snapshot.get("details_md") or ""),
                        ),
                        "actions_md": _merge_text(
                            str(vault_snapshot.get("actions_md") or ""),
                            str(app_snapshot.get("actions_md") or ""),
                        ),
                        "tags": _merge_lists(
                            [str(v) for v in (vault_snapshot.get("tags") or [])],
                            [str(v) for v in (app_snapshot.get("tags") or [])],
                        ),
                        "goals": _merge_lists(
                            [str(v) for v in (vault_snapshot.get("goals") or [])],
                            [str(v) for v in (app_snapshot.get("goals") or [])],
                        ),
                    }
                    merged_note = _snapshot_to_markdown(merged_snapshot, str(row["app_run_id"]))
                    manager.atomic_write_text(path, merged_note)

                    details["merge_metadata"] = {
                        "supersedes_id": [
                            f"vault:{row['vault_content_hash'] or 'unknown'}",
                            f"app:{row['db_content_hash'] or 'unknown'}",
                        ],
                        "entity_id": str(row["entity_id"]),
                        "merged_at": now,
                    }
                else:
                    app_snapshot["updated"] = now
                    app_note = _snapshot_to_markdown(app_snapshot, str(row["app_run_id"]))
                    manager.atomic_write_text(path, app_note)

                VaultIndexer(settings).index_paths([path])

        conn.execute(
            """
            UPDATE sync_conflicts
            SET conflict_status = ?, resolved_at = ?, details_json = ?
            WHERE conflict_id = ?
            """,
            (resolved_status, now, _json_dump(details), conflict_id),
        )

        event_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO sync_conflict_events (
              event_id, conflict_id, action, actor, source_run_id, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                conflict_id,
                resolved_status,
                actor or "local_user",
                row["app_run_id"],
                notes,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    resolved = get_conflict(settings, conflict_id)
    if not resolved:
        raise RuntimeError("Conflict resolved but could not be reloaded.")
    return resolved
