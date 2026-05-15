"""Tests for providers/instantaneous.py (Section 8.2)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.providers.instantaneous import (
    InstantaneousProvider,
)

from .conftest import make_history_result

ENTITY = "sensor.test_hr"


def _provider(hass: HomeAssistant, **overrides: object) -> InstantaneousProvider:
    cfg: dict[str, object] = {"entity_id": ENTITY, "aggregation": "mean"}
    cfg.update(overrides)
    return InstantaneousProvider(hass, cfg)


async def test_get_current_value_mean_uses_lts(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "65", {"unit_of_measurement": "bpm"})
    today = date(2026, 5, 15)
    with patch(
        "custom_components.morning_brief.providers.instantaneous.query",
        AsyncMock(return_value=make_history_result({today: 64.5})),
    ):
        result = await _provider(hass).get_current_value(today)
    assert result.raw == 64.5
    assert result.unit == "bpm"
    assert result.stale is False


async def test_get_current_value_mean_falls_back_to_live_state(hass: HomeAssistant) -> None:
    """LTS missing for today → fall back to current state value."""
    hass.states.async_set(ENTITY, "70", {"unit_of_measurement": "bpm"})
    today = date(2026, 5, 15)
    with patch(
        "custom_components.morning_brief.providers.instantaneous.query",
        AsyncMock(return_value=make_history_result({today: None}, status="insufficient_history")),
    ):
        result = await _provider(hass).get_current_value(today)
    assert result.raw == 70.0
    assert result.unit == "bpm"


async def test_get_current_value_last_uses_live_state(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "72", {"unit_of_measurement": "bpm"})
    result = await _provider(hass, aggregation="last").get_current_value(date(2026, 5, 15))
    assert result.raw == 72.0


async def test_unavailable_state_is_stale(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "unavailable")
    result = await _provider(hass, aggregation="last").get_current_value(date(2026, 5, 15))
    assert result.raw is None
    assert result.stale is True
    assert result.stale_reason == "no_data"


async def test_missing_entity_is_stale(hass: HomeAssistant) -> None:
    """Entity doesn't exist at all → stale, no crash (R8)."""
    result = await _provider(hass, aggregation="last").get_current_value(date(2026, 5, 15))
    assert result.raw is None
    assert result.stale is True


async def test_get_value_for_date_uses_lts(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "65", {"unit_of_measurement": "bpm"})
    target = date(2026, 5, 1)
    with patch(
        "custom_components.morning_brief.providers.instantaneous.query",
        AsyncMock(return_value=make_history_result({target: 60.0})),
    ):
        result = await _provider(hass).get_value_for_date(target)
    assert result.raw == 60.0


async def test_get_value_for_date_no_data_is_stale(hass: HomeAssistant) -> None:
    """Past date with no LTS → stale (no live-state fallback for past)."""
    hass.states.async_set(ENTITY, "65", {"unit_of_measurement": "bpm"})
    target = date(2026, 5, 1)
    with patch(
        "custom_components.morning_brief.providers.instantaneous.query",
        AsyncMock(return_value=make_history_result({target: None}, status="insufficient_history")),
    ):
        result = await _provider(hass).get_value_for_date(target)
    assert result.raw is None
    assert result.stale is True
    assert result.stale_reason == "no_data_for_date"


async def test_get_history_returns_per_day_field_values(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "65", {"unit_of_measurement": "bpm"})
    days = [date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3)]
    data = {days[0]: 60.0, days[1]: None, days[2]: 62.0}
    with patch(
        "custom_components.morning_brief.providers.instantaneous.query",
        AsyncMock(return_value=make_history_result(data)),
    ):
        out = await _provider(hass).get_history(days[0], days[2])
    assert out[days[0]].raw == 60.0
    assert out[days[1]].stale is True
    assert out[days[2]].raw == 62.0


def test_detect_from_entity_state_class_measurement(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "65", {"state_class": "measurement"})
    assert InstantaneousProvider.detect_from_entity(hass, ENTITY) == 0.8


def test_detect_from_entity_numeric_no_state_class(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "65", {})
    assert InstantaneousProvider.detect_from_entity(hass, ENTITY) == 0.4


def test_detect_from_entity_non_numeric_returns_zero(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "Bleu", {})
    assert InstantaneousProvider.detect_from_entity(hass, ENTITY) == 0.0


def test_validate_config_requires_entity_id(hass: HomeAssistant) -> None:
    assert InstantaneousProvider(hass, {}).validate_config() == ["entity_id is required"]


def test_validate_config_rejects_unknown_aggregation(hass: HomeAssistant) -> None:
    errors = InstantaneousProvider(
        hass, {"entity_id": ENTITY, "aggregation": "median"}
    ).validate_config()
    assert any("aggregation" in e for e in errors)
