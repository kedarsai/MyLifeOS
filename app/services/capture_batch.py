from __future__ import annotations

import re


_BLOCK_DELIMITER = re.compile(r"(?m)^\s*---\s*$")
_BLANK_BLOCKS = re.compile(r"\n{2,}")


def parse_batch_capture_text(raw_text: str) -> list[str]:
    text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    if _BLOCK_DELIMITER.search(text):
        chunks = _BLOCK_DELIMITER.split(text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    blocks = [chunk.strip() for chunk in _BLANK_BLOCKS.split(text) if chunk.strip()]
    if len(blocks) > 1:
        return blocks

    return [line.strip() for line in text.split("\n") if line.strip()]
