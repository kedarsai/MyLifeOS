from __future__ import annotations

from app.services.llm import _apply_openai_model_params


def _base_payload() -> dict:
    return {
        "text": {
            "format": {
                "type": "json_schema",
                "name": "demo_schema",
                "strict": True,
                "schema": {"type": "object"},
            }
        }
    }


def test_gpt5_mini_ignores_temperature_and_top_p() -> None:
    payload = _base_payload()
    _apply_openai_model_params(
        payload,
        params={
            "temperature": 0.2,
            "top_p": 0.8,
            "verbosity": "low",
            "max_output_tokens": 600,
        },
        model="gpt-5-mini",
    )
    assert "temperature" not in payload
    assert "top_p" not in payload
    assert payload["text"]["verbosity"] == "low"
    assert payload["max_output_tokens"] == 600


def test_gpt52_accepts_sampling_when_reasoning_effort_none() -> None:
    payload = _base_payload()
    _apply_openai_model_params(
        payload,
        params={
            "reasoning_effort": "none",
            "temperature": "0.4",
            "top_p": "0.9",
        },
        model="gpt-5.2",
    )
    assert payload["reasoning"]["effort"] == "none"
    assert payload["temperature"] == 0.4
    assert payload["top_p"] == 0.9


def test_gpt52_ignores_sampling_when_reasoning_effort_is_active() -> None:
    payload = _base_payload()
    _apply_openai_model_params(
        payload,
        params={
            "reasoning_effort": "low",
            "temperature": 0.4,
            "top_p": 0.8,
        },
        model="gpt-5.2",
    )
    assert payload["reasoning"]["effort"] == "low"
    assert "temperature" not in payload
    assert "top_p" not in payload
