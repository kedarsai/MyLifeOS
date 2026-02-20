from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.hashing import PAYLOAD_HASH_VERSION, canonical_payload_hash, content_hash_from_text
from app.db.engine import get_connection
from app.vault.markdown import ParsedMarkdownNote, parse_markdown_note


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else [], separators=(",", ":"), ensure_ascii=True)


@dataclass
class RebuildStats:
    files_scanned: int = 0
    entries_indexed: int = 0
    tasks_indexed: int = 0
    improvements_indexed: int = 0
    insights_indexed: int = 0
    chats_indexed: int = 0
    goals_indexed: int = 0
    reviews_indexed: int = 0


class VaultIndexer:
    def __init__(self, settings) -> None:
        self.settings = settings

    def rebuild(self) -> RebuildStats:
        stats = RebuildStats()
        conn = get_connection(self.settings)
        try:
            self._clear_rebuild_tables(conn)
            for path in sorted(self.settings.vault_path.rglob("*.md")):
                stats.files_scanned += 1
                self._index_file(conn, path, stats)
            self._rebuild_fts(conn)
            conn.commit()
            return stats
        finally:
            conn.close()

    def index_paths(self, paths: list[Path]) -> None:
        conn = get_connection(self.settings)
        try:
            stats = RebuildStats()
            for path in paths:
                self._index_file(conn, path, stats)
            self._rebuild_fts(conn)
            conn.commit()
        finally:
            conn.close()

    def _clear_rebuild_tables(self, conn) -> None:
        for table in (
            "chat_messages",
            "chat_threads",
            "insights",
            "improvements",
            "tasks",
            "obs_weight",
            "obs_food",
            "obs_sleep",
            "obs_activity",
            "goal_links",
            "goals",
            "weekly_reviews",
            "entries_index",
            "fts_entries_map",
            "sync_conflicts",
            "sync_conflict_events",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("INSERT INTO fts_entries(fts_entries) VALUES('delete-all')")

    def _index_file(self, conn, path: Path, stats: RebuildStats) -> None:
        text = path.read_text(encoding="utf-8")
        parsed = parse_markdown_note(text)
        fm = parsed.frontmatter
        if not fm:
            return

        entity_type = str(fm.get("entity_type", "")).strip().lower()
        if entity_type == "task":
            self._index_task(conn, path, parsed)
            stats.tasks_indexed += 1
            return
        if entity_type == "improvement":
            self._index_improvement(conn, path, parsed)
            stats.improvements_indexed += 1
            return
        if entity_type == "insight":
            self._index_insight(conn, path, parsed)
            stats.insights_indexed += 1
            return
        if entity_type == "chat_thread":
            self._index_chat_thread(conn, path, parsed)
            stats.chats_indexed += 1
            return
        if entity_type == "weekly_review":
            self._index_weekly_review(conn, path, parsed)
            stats.reviews_indexed += 1
            return

        if "goals" in path.parts:
            self._index_goal(conn, path, parsed)
            stats.goals_indexed += 1
            return
        if "reviews" in path.parts:
            self._index_weekly_review(conn, path, parsed)
            stats.reviews_indexed += 1
            return

        self._index_entry(conn, path, text, parsed)
        stats.entries_indexed += 1

    def _ensure_run(self, conn, run_id: str, run_kind: str = "rebuild") -> None:
        conn.execute(
            """
            INSERT INTO artifact_runs (run_id, run_kind, actor, notes_json)
            VALUES (?, ?, 'indexer', '{}')
            ON CONFLICT(run_id) DO NOTHING
            """,
            (run_id, run_kind),
        )

    def _fallback_run_id(self, path: Path, note_id: str) -> str:
        digest = hashlib.sha1(f"{path.as_posix()}:{note_id}".encode("utf-8")).hexdigest()[:16]
        return f"rebuild-{digest}"

    def _required_run_id(self, conn, path: Path, fm: dict[str, Any]) -> str:
        note_id = str(fm.get("id") or "")
        run_id = str(fm.get("source_run_id") or "").strip()
        if not run_id:
            run_id = self._fallback_run_id(path, note_id or "unknown")
        self._ensure_run(conn, run_id, "rebuild")
        return run_id

    def _coerce_bool(self, value: Any, default: bool = True) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        if value is None:
            return 1 if default else 0
        return 1 if str(value).strip().lower() in ("1", "true", "yes") else 0

    def _coerce_int(self, value: Any, default: int = 1) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _existing_goal_or_none(self, conn, goal_id: Any) -> Any:
        if not goal_id:
            return None
        exists = conn.execute(
            "SELECT 1 FROM goals WHERE goal_id = ?",
            (str(goal_id),),
        ).fetchone()
        return str(goal_id) if exists else None

    def _existing_entry_or_none(self, conn, entry_id: Any) -> Any:
        if not entry_id:
            return None
        exists = conn.execute(
            "SELECT 1 FROM entries_index WHERE id = ?",
            (str(entry_id),),
        ).fetchone()
        return str(entry_id) if exists else None

    def _demote_current(self, conn, table: str, logical_id: str, id_col: str, current_id: str) -> None:
        conn.execute(
            f"UPDATE {table} SET is_current = 0 WHERE logical_id = ? AND {id_col} <> ?",
            (logical_id, current_id),
        )

    def _index_entry(self, conn, path: Path, text: str, parsed: ParsedMarkdownNote) -> None:
        fm = parsed.frontmatter
        entry_id = str(fm.get("id") or "").strip()
        if not entry_id:
            return

        created_at = str(fm.get("created") or _utc_now())
        updated_at = str(fm.get("updated") or created_at)
        source_run_id = self._required_run_id(conn, path, fm)

        tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
        goals = fm.get("goals") if isinstance(fm.get("goals"), list) else []

        conn.execute(
            """
            INSERT INTO entries_index (
              id, path, created_at, updated_at, captured_tz, type, status, summary,
              raw_text, details_md, actions_md, tags_json, goals_json, source_run_id,
              content_hash, content_hash_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              path=excluded.path,
              created_at=excluded.created_at,
              updated_at=excluded.updated_at,
              captured_tz=excluded.captured_tz,
              type=excluded.type,
              status=excluded.status,
              summary=excluded.summary,
              raw_text=excluded.raw_text,
              details_md=excluded.details_md,
              actions_md=excluded.actions_md,
              tags_json=excluded.tags_json,
              goals_json=excluded.goals_json,
              source_run_id=excluded.source_run_id,
              content_hash=excluded.content_hash,
              content_hash_version=excluded.content_hash_version
            """,
            (
                entry_id,
                str(path),
                created_at,
                updated_at,
                fm.get("captured_tz"),
                str(fm.get("type") or "note"),
                str(fm.get("status") or "inbox"),
                fm.get("summary"),
                parsed.sections.get("Context (Raw)", ""),
                parsed.sections.get("Details", ""),
                parsed.sections.get("Actions", ""),
                _json_dump(tags),
                _json_dump(goals),
                source_run_id,
                content_hash_from_text(text),
                "sha256-v1",
            ),
        )

        for goal_id in goals:
            goal_exists = conn.execute(
                "SELECT 1 FROM goals WHERE goal_id = ?",
                (str(goal_id),),
            ).fetchone()
            if not goal_exists:
                continue
            conn.execute(
                """
                INSERT INTO goal_links (goal_id, entry_id, link_type)
                VALUES (?, ?, 'related')
                ON CONFLICT(goal_id, entry_id, link_type) DO NOTHING
                """,
                (str(goal_id), entry_id),
            )

    def _index_goal(self, conn, path: Path, parsed: ParsedMarkdownNote) -> None:
        fm = parsed.frontmatter
        goal_id = str(fm.get("goal_id") or fm.get("id") or "").strip()
        if not goal_id:
            return

        created_at = str(fm.get("created") or _utc_now())
        updated_at = str(fm.get("updated") or created_at)
        rules_md = parsed.sections.get("Rules", "")
        title = parsed.sections.get("Title", "").splitlines()
        name = (title[0].strip() if title else "") or str(fm.get("name") or goal_id)
        start_date = str(fm.get("start_date") or created_at[:10])
        end_date = fm.get("end_date")
        metrics = fm.get("metrics") if isinstance(fm.get("metrics"), list) else []
        status = str(fm.get("status") or "active")
        cadence = self._coerce_int(fm.get("review_cadence_days"), 7)

        conn.execute(
            """
            INSERT INTO goals (
              goal_id, path, name, start_date, end_date, rules_md, metrics_json,
              status, review_cadence_days, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(goal_id) DO UPDATE SET
              path=excluded.path,
              name=excluded.name,
              start_date=excluded.start_date,
              end_date=excluded.end_date,
              rules_md=excluded.rules_md,
              metrics_json=excluded.metrics_json,
              status=excluded.status,
              review_cadence_days=excluded.review_cadence_days,
              created_at=excluded.created_at,
              updated_at=excluded.updated_at
            """,
            (
                goal_id,
                str(path),
                name,
                start_date,
                end_date,
                rules_md,
                _json_dump(metrics),
                status,
                cadence,
                created_at,
                updated_at,
            ),
        )

    def _index_task(self, conn, path: Path, parsed: ParsedMarkdownNote) -> None:
        self._index_versioned_entity(conn, path, parsed, "tasks", "task_id")

    def _index_improvement(self, conn, path: Path, parsed: ParsedMarkdownNote) -> None:
        self._index_versioned_entity(conn, path, parsed, "improvements", "improvement_id")

    def _index_insight(self, conn, path: Path, parsed: ParsedMarkdownNote) -> None:
        self._index_versioned_entity(conn, path, parsed, "insights", "insight_id")

    def _index_versioned_entity(
        self, conn, path: Path, parsed: ParsedMarkdownNote, table: str, id_col: str
    ) -> None:
        fm = parsed.frontmatter
        record_id = str(fm.get("id") or "").strip()
        if not record_id:
            return

        logical_id = str(fm.get("logical_id") or record_id)
        source_run_id = self._required_run_id(conn, path, fm)
        version_no = self._coerce_int(fm.get("version_no"), 1)
        is_current = self._coerce_bool(fm.get("is_current"), True)
        supersedes_id = fm.get("supersedes_id")
        created_at = str(fm.get("created") or _utc_now())
        updated_at = str(fm.get("updated") or created_at)
        goal_id = self._existing_goal_or_none(conn, fm.get("goal_id"))
        source_entry_id = self._existing_entry_or_none(conn, fm.get("source_entry_id"))

        title = parsed.sections.get("Title", "").splitlines()
        title = title[0].strip() if title else str(fm.get("title") or record_id)
        rationale = parsed.sections.get("Rationale", "")
        evidence_lines = parsed.sections.get("Evidence", "")
        if evidence_lines:
            evidence_json = _json_dump([line.strip("- ").strip() for line in evidence_lines.splitlines() if line.strip()])
        else:
            evidence_json = "[]"

        payload_seed = {
            "table": table,
            "logical_id": logical_id,
            "title": title,
            "goal_id": goal_id,
            "source_entry_id": source_entry_id,
            "rationale": rationale,
            "evidence_json": evidence_json,
            "status": fm.get("status"),
            "priority": fm.get("priority"),
            "due_date": fm.get("due_date"),
        }
        payload_hash = str(fm.get("payload_hash") or canonical_payload_hash(payload_seed))
        payload_hash_version = str(fm.get("payload_hash_version") or PAYLOAD_HASH_VERSION)

        if is_current:
            self._demote_current(conn, table, logical_id, id_col, record_id)

        if table == "tasks":
            conn.execute(
                """
                INSERT INTO tasks (
                  task_id, logical_id, path, source_entry_id, source_run_id, goal_id, title,
                  due_date, priority, status, rationale, payload_hash, payload_hash_version,
                  version_no, is_current, supersedes_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                  logical_id=excluded.logical_id,
                  path=excluded.path,
                  source_entry_id=excluded.source_entry_id,
                  source_run_id=excluded.source_run_id,
                  goal_id=excluded.goal_id,
                  title=excluded.title,
                  due_date=excluded.due_date,
                  priority=excluded.priority,
                  status=excluded.status,
                  rationale=excluded.rationale,
                  payload_hash=excluded.payload_hash,
                  payload_hash_version=excluded.payload_hash_version,
                  version_no=excluded.version_no,
                  is_current=excluded.is_current,
                  supersedes_id=excluded.supersedes_id,
                  created_at=excluded.created_at,
                  updated_at=excluded.updated_at
                """,
                (
                    record_id,
                    logical_id,
                    str(path),
                    source_entry_id,
                    source_run_id,
                    goal_id,
                    title,
                    fm.get("due_date"),
                    str(fm.get("priority") or "medium"),
                    str(fm.get("status") or "open"),
                    rationale,
                    payload_hash,
                    payload_hash_version,
                    version_no,
                    is_current,
                    supersedes_id,
                    created_at,
                    updated_at,
                ),
            )
            return

        if table == "improvements":
            conn.execute(
                """
                INSERT INTO improvements (
                  improvement_id, logical_id, path, source_entry_id, source_run_id, goal_id,
                  title, rationale, status, last_nudged_at, payload_hash, payload_hash_version,
                  version_no, is_current, supersedes_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(improvement_id) DO UPDATE SET
                  logical_id=excluded.logical_id,
                  path=excluded.path,
                  source_entry_id=excluded.source_entry_id,
                  source_run_id=excluded.source_run_id,
                  goal_id=excluded.goal_id,
                  title=excluded.title,
                  rationale=excluded.rationale,
                  status=excluded.status,
                  last_nudged_at=excluded.last_nudged_at,
                  payload_hash=excluded.payload_hash,
                  payload_hash_version=excluded.payload_hash_version,
                  version_no=excluded.version_no,
                  is_current=excluded.is_current,
                  supersedes_id=excluded.supersedes_id,
                  created_at=excluded.created_at,
                  updated_at=excluded.updated_at
                """,
                (
                    record_id,
                    logical_id,
                    str(path),
                    source_entry_id,
                    source_run_id,
                    goal_id,
                    title,
                    rationale or "-",
                    str(fm.get("status") or "open"),
                    fm.get("last_nudged_at"),
                    payload_hash,
                    payload_hash_version,
                    version_no,
                    is_current,
                    supersedes_id,
                    created_at,
                    updated_at,
                ),
            )
            return

        conn.execute(
            """
            INSERT INTO insights (
              insight_id, logical_id, path, source_entry_id, source_run_id, goal_id, title,
              evidence_json, payload_hash, payload_hash_version, version_no, is_current,
              supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(insight_id) DO UPDATE SET
              logical_id=excluded.logical_id,
              path=excluded.path,
              source_entry_id=excluded.source_entry_id,
              source_run_id=excluded.source_run_id,
              goal_id=excluded.goal_id,
              title=excluded.title,
              evidence_json=excluded.evidence_json,
              payload_hash=excluded.payload_hash,
              payload_hash_version=excluded.payload_hash_version,
              version_no=excluded.version_no,
              is_current=excluded.is_current,
              supersedes_id=excluded.supersedes_id,
              created_at=excluded.created_at,
              updated_at=excluded.updated_at
            """,
            (
                record_id,
                logical_id,
                str(path),
                source_entry_id,
                source_run_id,
                goal_id,
                title,
                evidence_json,
                payload_hash,
                payload_hash_version,
                version_no,
                is_current,
                supersedes_id,
                created_at,
                updated_at,
            ),
        )

    def _index_chat_thread(self, conn, path: Path, parsed: ParsedMarkdownNote) -> None:
        fm = parsed.frontmatter
        thread_id = str(fm.get("id") or "").strip()
        if not thread_id:
            return

        logical_id = str(fm.get("logical_id") or thread_id)
        source_run_id = self._required_run_id(conn, path, fm)
        version_no = self._coerce_int(fm.get("version_no"), 1)
        is_current = self._coerce_bool(fm.get("is_current"), True)
        supersedes_id = fm.get("supersedes_id")
        created_at = str(fm.get("created") or _utc_now())
        updated_at = str(fm.get("updated") or created_at)
        goal_id = self._existing_goal_or_none(conn, fm.get("goal_id"))

        title = str(fm.get("title") or "")
        if not title:
            meta = parsed.sections.get("Thread Meta", "")
            for line in meta.splitlines():
                if line.lower().strip().startswith("- title:"):
                    title = line.split(":", 1)[1].strip()
                    break
        title = title or thread_id

        if is_current:
            self._demote_current(conn, "chat_threads", logical_id, "thread_id", thread_id)

        conn.execute(
            """
            INSERT INTO chat_threads (
              thread_id, logical_id, path, source_run_id, goal_id, title,
              version_no, is_current, supersedes_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
              logical_id=excluded.logical_id,
              path=excluded.path,
              source_run_id=excluded.source_run_id,
              goal_id=excluded.goal_id,
              title=excluded.title,
              version_no=excluded.version_no,
              is_current=excluded.is_current,
              supersedes_id=excluded.supersedes_id,
              created_at=excluded.created_at,
              updated_at=excluded.updated_at
            """,
            (
                thread_id,
                logical_id,
                str(path),
                source_run_id,
                goal_id,
                title,
                version_no,
                is_current,
                supersedes_id,
                created_at,
                updated_at,
            ),
        )

    def _parse_bullets(self, text: str) -> list[str]:
        out = []
        for line in (text or "").splitlines():
            clean = line.strip()
            if clean.startswith("- "):
                out.append(clean[2:].strip())
        return out

    def _index_weekly_review(self, conn, path: Path, parsed: ParsedMarkdownNote) -> None:
        fm = parsed.frontmatter
        goal_id = str(fm.get("goal_id") or "").strip()
        if not goal_id:
            return
        review_id = str(fm.get("id") or f"review-{goal_id}-{fm.get('week_start') or 'unknown'}")
        week_start = str(fm.get("week_start") or "")
        week_end = str(fm.get("week_end") or "")
        if not week_start or not week_end:
            return
        source_run_id = self._required_run_id(conn, path, fm)

        snapshot_raw = parsed.sections.get("Snapshot", "{}")
        try:
            snapshot = json.loads(snapshot_raw) if snapshot_raw.strip() else {}
        except json.JSONDecodeError:
            snapshot = {}

        review_obj = {
            "what_went_well": self._parse_bullets(parsed.sections.get("What's Going Well", "")),
            "what_did_not_go_well": self._parse_bullets(parsed.sections.get("What's Not Going Well", "")),
            "patterns": self._parse_bullets(parsed.sections.get("Patterns", "")),
            "next_best_actions": [{"title": x, "priority": "medium"} for x in self._parse_bullets(parsed.sections.get("Next Actions", ""))],
            "risk_level": "medium",
            "confidence": 0.7,
        }

        conn.execute(
            """
            INSERT INTO weekly_reviews (
              review_id, goal_id, path, week_start, week_end, snapshot_json,
              review_json, source_run_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(goal_id, week_start, week_end) DO UPDATE SET
              review_id=excluded.review_id,
              path=excluded.path,
              snapshot_json=excluded.snapshot_json,
              review_json=excluded.review_json,
              source_run_id=excluded.source_run_id,
              created_at=excluded.created_at
            """,
            (
                review_id,
                goal_id,
                str(path),
                week_start,
                week_end,
                _json_dump(snapshot),
                _json_dump(review_obj),
                source_run_id,
                str(fm.get("created") or _utc_now()),
            ),
        )

    def _rebuild_fts(self, conn) -> None:
        conn.execute("INSERT INTO fts_entries(fts_entries) VALUES('delete-all')")
        conn.execute("DELETE FROM fts_entries_map")
        rows = conn.execute(
            """
            SELECT id, summary, raw_text, details_md, tags_json, goals_json
            FROM entries_index
            WHERE status != 'archived'
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()

        rowid = 1
        for row in rows:
            conn.execute(
                """
                INSERT INTO fts_entries (rowid, summary, raw_text, details_md, tags, goals)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rowid,
                    row["summary"] or "",
                    row["raw_text"] or "",
                    row["details_md"] or "",
                    row["tags_json"] or "[]",
                    row["goals_json"] or "[]",
                ),
            )
            conn.execute(
                "INSERT INTO fts_entries_map (entry_id, fts_rowid) VALUES (?, ?)",
                (row["id"], rowid),
            )
            rowid += 1
