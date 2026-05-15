"""Tests for providers/cumulative.py (Section 8.1)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.providers.cumulative import CumulativeProvider

from .conftest import make_history_result

ENTITY = "sensor.daily_steps"


def _provider(hass: HomeAssistant, **overrides: object) -> CumulativeProvider:
    cfg: dict[str, object] = {"entity_id": ENTITY, "reset_hour": 0}
    cfg.update(overrides)
    return CumulativeProvider(hass, cfg)


async def test_get_current_value_uses_lts_change(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "5000", {"unit_of_measurement": "steps"})
    today = date(2026, 5, 15)
    with patch(
        "custom_components.morning_brief.providers.cumulative.query",
        AsyncMock(return_value=make_history_result({today: 7423.0})),
    ) as q:
        result = await _provider(hass).get_current_value(today)
    assert result.raw == 7423.0
    assert result.unit == "steps"
    # Verify the aggregation passed to history.query is "change".
    assert q.await_args.args[1].aggregation == "change"


async def test_get_value_for_date_no_data_is_stale(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "5000", {})
    target = date(2026, 5, 1)
    with patch(
        "custom_components.morning_brief.providers.cumulative.query",
        AsyncMock(return_value=make_history_result({target: None}, status="insufficient_history")),
    ):
        result = await _provider(hass).get_value_for_date(target)
    assert result.raw is None
    assert result.stale is True


async def test_get_history_returns_per_day(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "5000", {"unit_of_measurement": "steps"})
    days = [date(2026, 5, 1), date(2026, 5, 2)]
    with patch(
        "custom_components.morning_brief.providers.cumulative.query",
        AsyncMock(return_value=make_history_result({days[0]: 6000.0, days[1]: 7100.0})),
    ):
        out = await _provider(hass).get_history(days[0], days[1])
    assert out[days[0]].raw == 6000.0
    assert out[days[1]].raw == 7100.0


def test_detect_from_entity_total_increasing(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "1", {"state_class": "total_increasing"})
    assert CumulativeProvider.detect_from_entity(hass, ENTITY) == 0.9


def test_detect_from_entity_total_with_energy_device_class(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "sensor.kwh", "1", {"state_class": "total", "device_class": "energy"}
    )
    assert CumulativeProvider.detect_from_entity(hass, "sensor.kwh") == 0.7


def test_detect_from_entity_returns_zero_otherwise(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    assert CumulativeProvider.detect_from_entity(hass, ENTITY) == 0.0


def test_validate_config_rejects_invalid_reset_hour(hass: HomeAssistant) -> None:
    errors = CumulativeProvider(
        hass, {"entity_id": ENTITY, "reset_hour": 26}
    ).validate_config()
    assert any("reset_hour" in e for e in errors)
