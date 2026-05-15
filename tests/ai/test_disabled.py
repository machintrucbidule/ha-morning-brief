"""Tests for ai/disabled.py (Section 13.2)."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.ai.disabled import DisabledProvider


async def test_generate_returns_valid_empty_envelope(hass: HomeAssistant) -> None:
    result = await DisabledProvider(hass, {}).generate("any prompt", "en")
    assert result.status == "ok"
    assert result.tokens_used == 0
    payload = json.loads(result.content or "")
    assert payload == {
        "alertes_formulees": [],
        "insights": {},
        "weather_synthesis": "",
        "verdict": "",
    }


async def test_validate_credentials_always_true(hass: HomeAssistant) -> None:
    assert await DisabledProvider(hass, {}).validate_credentials() is True


async def test_provider_type_is_disabled(hass: HomeAssistant) -> None:
    assert DisabledProvider(hass, {}).provider_type == "disabled"
