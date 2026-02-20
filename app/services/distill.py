from __future__ import annotations

import re


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CHECKBOX_LINE_RE = re.compile(r"^\s*-\s*\[\s*[xX ]\s*\]\s*(.+?)\s*$")
_INLINE_TASK_RE = re.compile(r"\b(?:todo|action)\s*:\s*([^.;\n]+(?:\s+due:\d{4}-\d{2}-\d{2})?)", re.IGNORECASE)
_INTENT_PATTERNS = [
    re.compile(r"^(?:i\s+)?need\s+to\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:i\s+)?want\s+to\s+(.+)$", re.IGNORECASE),
    re.compile(r"^would\s+like\s+to\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:i\s+)?plan\s+to\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:i\s+)?must\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:i\s+)?have\s+to\s+(.+)$", re.IGNORECASE),
]


def _compact(text: str) -> str:
    return " ".join((text or "").strip().split())


def _summary(raw_text: str, max_len: int = 140) -> str:
    cleaned = _compact(raw_text)
    if not cleaned:
        return "Processed note"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


def _details(raw_text: str) -> str:
    cleaned = _compact(raw_text)
    if not cleaned:
        return "-"
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(cleaned) if part.strip()]
    chosen = sentences[:3] if sentences else [cleaned]
    return "\n".join(f"- {line}" for line in chosen)


def _actions(raw_text: str) -> str:
    def clean_action(value: str) -> str:
        item = _compact(value).strip(" .-")
        if item.lower().startswith("to "):
            item = item[3:].strip()
        if len(item) > 200:
            item = item[:197] + "..."
        return item

    lines = [line.strip() for line in (raw_text or "").splitlines() if line.strip()]
    explicit: list[str] = []
    for line in lines:
        checkbox_match = _CHECKBOX_LINE_RE.match(line)
        if checkbox_match:
            explicit.append(checkbox_match.group(1).strip())
        for match in _INLINE_TASK_RE.finditer(line):
            explicit.append(match.group(1).strip())

    cleaned = _compact(raw_text)
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(cleaned) if part.strip()]
    for sentence in sentences:
        for pattern in _INTENT_PATTERNS:
            match = pattern.match(sentence)
            if not match:
                continue
            explicit.append(match.group(1).strip())
            break

    deduped: list[str] = []
    seen: set[str] = set()
    for item in explicit:
        cleaned_item = clean_action(item)
        key = cleaned_item.lower()
        if not cleaned_item or key in seen:
            continue
        deduped.append(cleaned_item)
        seen.add(key)
    if deduped:
        return "\n".join(f"- [ ] {item}" for item in deduped)
    return "-"


def _tags(raw_text: str, existing: list[str]) -> list[str]:
    text = (raw_text or "").lower()
    derived = []
    if "sleep" in text:
        derived.append("sleep")
    if "workout" in text or "exercise" in text or "run " in text:
        derived.append("fitness")
    if "project" in text or "code" in text:
        derived.append("project")
    merged = []
    for value in [*(existing or []), *derived]:
        tag = str(value).strip()
        if tag and tag not in merged:
            merged.append(tag)
    return merged


def distill_raw_text(raw_text: str, existing_tags: list[str] | None = None) -> dict:
    return {
        "summary": _summary(raw_text),
        "details_md": _details(raw_text),
        "actions_md": _actions(raw_text),
        "tags": _tags(raw_text, existing_tags or []),
    }
