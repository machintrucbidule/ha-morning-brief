"""Tests for providers/state.py (Section 8.4)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.history import StateChange
from custom_components.morning_brief.providers.state import StateProvider

ENTITY = "sensor.tempo_color"


async def test_get_current_value_returns_state(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "Bleu")
    result = await StateProvider(hass, {"entity_id": ENTITY}).get_current_value(
        date(2026, 5, 15)
    )
    assert result.raw == "Bleu"
    assert result.stale is False


async def test_get_current_value_applies_state_mapping(hass: HomeAssistant) -> None:
    """The mapping entry rides along in `extra` for the card to render."""
    hass.states.async_set(ENTITY, "Rouge")
    cfg = {
        "entity_id": ENTITY,
        "state_mapping": {
            "Rouge": {"label": "Red", "icon": "🔴", "color": "#e84444"},
        },
    }
    result = await StateProvider(hass, cfg).get_current_value(date(2026, 5, 15))
    assert result.extra["mapping"]["label"] == "Red"
    assert result.extra["mapping"]["icon"] == "🔴"


async def test_unavailable_state_is_stale(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "unavailable")
    result = await StateProvider(hass, {"entity_id": ENTITY}).get_current_value(
        date(2026, 5, 15)
    )
    assert result.raw is None
    assert result.stale is True


async def test_get_value_for_date_uses_last_state_at_end_of_day(
    hass: HomeAssistant,
) -> None:
    target = date(2026, 5, 1)
    end_of_day = dt_util.start_of_local_day(target) + timedelta(hours=22)
    changes = [
        StateChange(timestamp=end_of_day - timedelta(hours=4), state="Bleu", attributes={}),
        StateChange(timestamp=end_of_day - timedelta(hours=1), state="Rouge", attributes={}),
    ]
    with patch(
        "custom_components.morning_brief.providers.state.get_short_term",
        AsyncMock(return_value=changes),
    ):
        result = await StateProvider(hass, {"entity_id": ENTITY}).get_value_for_date(target)
    assert result.raw == "Rouge"


async def test_get_value_for_date_no_history_is_stale(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.morning_brief.providers.state.get_short_term",
        AsyncMock(return_value=[]),
    ):
        result = await StateProvider(hass, {"entity_id": ENTITY}).get_value_for_date(
            date(2026, 5, 1)
        )
    assert result.raw is None
    assert result.stale is True


async def test_get_value_for_date_filters_unavailable(hass: HomeAssistant) -> None:
    target = date(2026, 5, 1)
    end_of_day = dt_util.start_of_local_day(target) + timedelta(hours=22)
    changes = [
        StateChange(
            timestamp=end_of_day - timedelta(hours=4), state="Bleu", attributes={}
        ),
        StateChange(
            timestamp=end_of_day - timedelta(hours=1),
            state="unavailable",
            attributes={},
        ),
    ]
    with patch(
        "custom_components.morning_brief.providers.state.get_short_term",
        AsyncMock(return_value=changes),
    ):
        result = await StateProvider(hass, {"entity_id": ENTITY}).get_value_for_date(target)
    assert result.raw == "Bleu"


def test_detect_from_entity_binary_sensor(hass: HomeAssistant) -> None:
    assert StateProvider.detect_from_entity(hass, "binary_sensor.x") == 0.5


def test_detect_from_entity_non_numeric(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.color", "Rouge")
    assert StateProvider.detect_from_entity(hass, "sensor.color") == 0.6


def test_validate_config_rejects_non_dict_mapping(hass: HomeAssistant) -> None:
    errors = StateProvider(
        hass, {"entity_id": ENTITY, "state_mapping": "not a dict"}
    ).validate_config()
    assert any("state_mapping" in e for e in errors)


# Silence unused-import warning if datetime isn't referenced above.
_ = datetime
