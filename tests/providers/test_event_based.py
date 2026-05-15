"""Tests for providers/event_based.py (Section 8.3)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.history import StateChange
from custom_components.morning_brief.providers.event_based import EventBasedProvider

ENTITY = "sensor.scale_weight"


def _change(state: str, days_ago: int, hour: int = 8) -> StateChange:
    """Build a StateChange `days_ago` days before the logical day, at `hour:00` local."""
    today = date(2026, 5, 15)
    base = dt_util.start_of_local_day(today - timedelta(days=days_ago))
    return StateChange(
        timestamp=base + timedelta(hours=hour), state=state, attributes={}
    )


async def test_event_today_marks_value_fresh(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "75", {"unit_of_measurement": "kg"})
    today = date(2026, 5, 15)
    with patch(
        "custom_components.morning_brief.providers.event_based.get_short_term",
        AsyncMock(return_value=[_change("75", days_ago=0, hour=7)]),
    ):
        result = await EventBasedProvider(
            hass, {"entity_id": ENTITY}
        ).get_current_value(today)
    assert result.raw == 75.0
    assert result.unit == "kg"
    assert result.stale is False


async def test_event_yesterday_marks_no_event_today(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "75", {"unit_of_measurement": "kg"})
    today = date(2026, 5, 15)
    with patch(
        "custom_components.morning_brief.providers.event_based.get_short_term",
        AsyncMock(return_value=[_change("74.6", days_ago=1)]),
    ):
        result = await EventBasedProvider(
            hass, {"entity_id": ENTITY}
        ).get_current_value(today)
    assert result.raw == 74.6
    assert result.stale is True
    assert result.stale_reason == "no_event_today"


async def test_no_events_returns_no_data_stale(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "75", {"unit_of_measurement": "kg"})
    today = date(2026, 5, 15)
    with patch(
        "custom_components.morning_brief.providers.event_based.get_short_term",
        AsyncMock(return_value=[]),
    ):
        result = await EventBasedProvider(
            hass, {"entity_id": ENTITY}
        ).get_current_value(today)
    assert result.raw is None
    assert result.stale is True
    assert result.stale_reason == "no_data"


async def test_epsilon_dedupes_consecutive_close_values(hass: HomeAssistant) -> None:
    """epsilon=0.1: a 0.05 delta should be filtered before "last event" pickup."""
    hass.states.async_set(ENTITY, "75", {"unit_of_measurement": "kg"})
    today = date(2026, 5, 15)
    changes = [
        _change("75.00", days_ago=0, hour=7),
        _change("75.05", days_ago=0, hour=8),  # within epsilon → dropped
    ]
    with patch(
        "custom_components.morning_brief.providers.event_based.get_short_term",
        AsyncMock(return_value=changes),
    ):
        result = await EventBasedProvider(
            hass, {"entity_id": ENTITY, "epsilon": 0.1, "min_debounce_minutes": 0}
        ).get_current_value(today)
    assert result.raw == 75.00


async def test_unavailable_filtered_in_event_stream(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "75", {"unit_of_measurement": "kg"})
    today = date(2026, 5, 15)
    changes = [
        _change("75.0", days_ago=0, hour=7),
        _change("unavailable", days_ago=0, hour=8),
    ]
    with patch(
        "custom_components.morning_brief.providers.event_based.get_short_term",
        AsyncMock(return_value=changes),
    ):
        result = await EventBasedProvider(
            hass, {"entity_id": ENTITY, "min_debounce_minutes": 0}
        ).get_current_value(today)
    assert result.raw == 75.0
    assert result.stale is False


async def test_get_value_for_date_returns_most_recent_event(hass: HomeAssistant) -> None:
    target = date(2026, 5, 1)
    base = dt_util.start_of_local_day(target) + timedelta(hours=10)
    changes = [
        StateChange(timestamp=base, state="74.0", attributes={}),
        StateChange(timestamp=base + timedelta(hours=2), state="74.5", attributes={}),
    ]
    with patch(
        "custom_components.morning_brief.providers.event_based.get_short_term",
        AsyncMock(return_value=changes),
    ):
        result = await EventBasedProvider(
            hass, {"entity_id": ENTITY, "min_debounce_minutes": 0}
        ).get_value_for_date(target)
    assert result.raw == 74.5


def test_detect_from_entity_weight_no_state_class(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.scale", "75", {"device_class": "weight"})
    assert EventBasedProvider.detect_from_entity(hass, "sensor.scale") == 0.7


def test_detect_from_entity_state_class_returns_zero(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "sensor.scale", "75", {"device_class": "weight", "state_class": "measurement"}
    )
    assert EventBasedProvider.detect_from_entity(hass, "sensor.scale") == 0.0


def test_validate_config_rejects_negative_epsilon(hass: HomeAssistant) -> None:
    errors = EventBasedProvider(
        hass, {"entity_id": ENTITY, "epsilon": -1.0}
    ).validate_config()
    assert any("epsilon" in e for e in errors)
