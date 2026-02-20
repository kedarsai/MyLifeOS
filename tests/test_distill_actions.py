from __future__ import annotations

from app.services.distill import distill_raw_text


def test_distill_extracts_inline_todo_and_intent_actions() -> None:
    output = distill_raw_text(
        "Built feature. TODO: ship v1 due:2026-02-20. I need to update docs.",
        existing_tags=[],
    )
    actions = output["actions_md"]
    assert "- [ ] ship v1 due:2026-02-20" in actions
    assert "- [ ] update docs" in actions


def test_distill_does_not_emit_generic_placeholder_action() -> None:
    output = distill_raw_text("Testing the app now, looks fine and impressive.", existing_tags=[])
    assert output["actions_md"] == "-"
