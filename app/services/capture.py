from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.time import utc_now_iso
from app.vault.manager import VaultManager, slugify
from app.vault.markdown import render_entry_note


@dataclass
class CaptureResult:
    entry_id: str
    source_run_id: str
    path: Path
    created: str


def _safe_summary(raw_text: str, max_len: int = 180) -> str:
    first_line = (raw_text or "").strip().splitlines()
    text = first_line[0] if first_line else ""
    if not text:
        return "Captured note"
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def capture_entry(
    settings: Settings,
    raw_text: str,
    entry_type: str = "note",
    tags: list[str] | None = None,
    goals: list[str] | None = None,
    created_override: str | None = None,
) -> CaptureResult:
    manager = VaultManager(settings)
    manager.ensure_layout()

    entry_id = manager.new_entry_id()
    source_run_id = f"manual-{uuid.uuid4()}"
    created = created_override or manager.default_created_iso()

    frontmatter = {
        "id": entry_id,
        "created": created,
        "type": entry_type,
        "status": "inbox",
        "goals": goals or [],
        "tags": tags or [],
        "summary": _safe_summary(raw_text),
        "source_run_id": source_run_id,
    }
    note_text = render_entry_note(
        frontmatter=frontmatter,
        details="-",
        actions="-",
        raw_text=raw_text,
        ai_text=f"Prompt: n/a\nRunId: {source_run_id}\nCapturedAt: {utc_now_iso()}",
    )

    slug = slugify(frontmatter["summary"])
    path = manager.build_entry_path(created, entry_type, slug)
    manager.atomic_write_text(path, note_text)

    return CaptureResult(
        entry_id=entry_id,
        source_run_id=source_run_id,
        path=path,
        created=created,
    )
