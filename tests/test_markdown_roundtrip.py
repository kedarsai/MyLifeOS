from app.vault.markdown import parse_markdown_note, render_entry_note


def test_raw_text_roundtrip_is_preserved() -> None:
    raw = "Line 1\n  Line 2 with spaces\n\nLine 4"
    note = render_entry_note(
        frontmatter={
            "id": "entry-1",
            "created": "2026-02-19T10:00:00+00:00",
            "type": "note",
            "status": "inbox",
            "goals": [],
            "tags": [],
            "summary": "Test",
            "source_run_id": "manual-1",
        },
        details="-",
        actions="-",
        raw_text=raw,
        ai_text=None,
    )

    parsed = parse_markdown_note(note)
    assert parsed.raw_text == raw

