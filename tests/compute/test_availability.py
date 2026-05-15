"""Tests for compute/availability.py (Section 9)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.compute.availability import apply_gate
from custom_components.morning_brief.providers.base import FieldProvider
from custom_components.morning_brief.types import AvailabilityGate, FieldValue

GATE_ENTITY = "binary_sensor.is_sleeping"


def _fresh_value() -> FieldValue:
    return FieldValue(raw=451, unit="min", stale=False, as_of=datetime.now(UTC))


def _previous_value() -> FieldValue:
    return FieldValue(
        raw=420,
        unit="min",
        stale=False,
        as_of=datetime.now(UTC) - timedelta(days=1),
    )


def _provider_returning(prev: FieldValue) -> MagicMock:
    """Mock provider whose get_value_for_date returns ``prev``."""
    prov = MagicMock(spec=FieldProvider)
    prov.get_value_for_date = AsyncMock(return_value=prev)
    return prov


async def test_no_gate_returns_value_unchanged(hass: HomeAssistant) -> None:
    fv = _fresh_value()
    result = await apply_gate(
        hass, fv, None, date(2026, 5, 15), _provider_returning(_previous_value())
    )
    assert result is fv


async def test_gate_satisfied_returns_value_unchanged(hass: HomeAssistant) -> None:
    """gate_entity == expected_state → original value passes through."""
    hass.states.async_set(GATE_ENTITY, "off")
    fv = _fresh_value()
    gate = AvailabilityGate(entity_id=GATE_ENTITY, expected_state="off")
    result = await apply_gate(
        hass, fv, gate, date(2026, 5, 15), _provider_returning(_previous_value())
    )
    assert result is fv


async def test_gate_not_satisfied_returns_previous_day_stale(hass: HomeAssistant) -> None:
    hass.states.async_set(GATE_ENTITY, "on")  # still sleeping
    gate = AvailabilityGate(entity_id=GATE_ENTITY, expected_state="off")
    prev = _previous_value()
    result = await apply_gate(
        hass, _fresh_value(), gate, date(2026, 5, 15), _provider_returning(prev)
    )
    assert result.raw == prev.raw
    assert result.unit == prev.unit
    assert result.stale is True
    assert result.stale_reason == "awaiting_availability"


async def test_gate_sensor_unavailable_returns_previous_day_stale(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(GATE_ENTITY, "unavailable")
    gate = AvailabilityGate(entity_id=GATE_ENTITY, expected_state="off")
    prev = _previous_value()
    result = await apply_gate(
        hass, _fresh_value(), gate, date(2026, 5, 15), _provider_returning(prev)
    )
    assert result.raw == prev.raw
    assert result.stale is True
    assert result.stale_reason == "gate_sensor_unavailable"


async def test_gate_sensor_missing_returns_previous_day_stale(hass: HomeAssistant) -> None:
    """No entity at all → treated like unavailable (G5 conservative)."""
    gate = AvailabilityGate(entity_id="binary_sensor.does_not_exist", expected_state="off")
    prev = _previous_value()
    result = await apply_gate(
        hass, _fresh_value(), gate, date(2026, 5, 15), _provider_returning(prev)
    )
    assert result.stale is True
    assert result.stale_reason == "gate_sensor_unavailable"


async def test_provider_get_value_for_date_called_with_logical_minus_one(
    hass: HomeAssistant,
) -> None:
    """The fallback queries the calendar day BEFORE logical_date."""
    hass.states.async_set(GATE_ENTITY, "on")
    gate = AvailabilityGate(entity_id=GATE_ENTITY, expected_state="off")
    prov = _provider_returning(_previous_value())
    await apply_gate(hass, _fresh_value(), gate, date(2026, 5, 15), prov)
    prov.get_value_for_date.assert_awaited_once_with(date(2026, 5, 14))
