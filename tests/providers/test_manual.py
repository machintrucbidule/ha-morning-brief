"""Tests for providers/manual.py (Section 8.8)."""

from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.providers.manual import ManualProvider


async def test_input_number_returns_float(hass: HomeAssistant) -> None:
    eid = "input_number.mood"
    hass.states.async_set(eid, "7.5", {"unit_of_measurement": "/10"})
    result = await ManualProvider(hass, {"entity_id": eid}).get_current_value(
        date(2026, 5, 15)
    )
    assert result.raw == 7.5
    assert result.unit == "/10"


async def test_input_text_returns_string(hass: HomeAssistant) -> None:
    eid = "input_text.daily_intent"
    hass.states.async_set(eid, "Be kind")
    result = await ManualProvider(hass, {"entity_id": eid}).get_current_value(
        date(2026, 5, 15)
    )
    assert result.raw == "Be kind"


async def test_input_datetime_returns_isoformat(hass: HomeAssistant) -> None:
    eid = "input_datetime.last_check"
    hass.states.async_set(eid, "2026-05-10T08:00:00+00:00")
    result = await ManualProvider(hass, {"entity_id": eid}).get_current_value(
        date(2026, 5, 15)
    )
    assert isinstance(result.raw, str)
    assert "2026-05-10T08:00:00" in result.raw


async def test_unavailable_state_is_stale(hass: HomeAssistant) -> None:
    eid = "input_number.mood"
    hass.states.async_set(eid, "unavailable")
    result = await ManualProvider(hass, {"entity_id": eid}).get_current_value(
        date(2026, 5, 15)
    )
    assert result.raw is None
    assert result.stale is True


async def test_input_text_value_for_past_date_is_stale(hass: HomeAssistant) -> None:
    """Text inputs aren't queryable historically — past returns stale."""
    eid = "input_text.daily_intent"
    hass.states.async_set(eid, "Be kind")
    result = await ManualProvider(hass, {"entity_id": eid}).get_value_for_date(
        date(2026, 5, 1)
    )
    assert result.raw is None
    assert result.stale is True


def test_detect_from_entity_input_number_high_score(hass: HomeAssistant) -> None:
    assert ManualProvider.detect_from_entity(hass, "input_number.x") == 0.8


def test_detect_from_entity_input_text_lower_score(hass: HomeAssistant) -> None:
    assert ManualProvider.detect_from_entity(hass, "input_text.x") == 0.6


def test_detect_from_entity_unrelated_returns_zero(hass: HomeAssistant) -> None:
    assert ManualProvider.detect_from_entity(hass, "sensor.x") == 0.0


def test_validate_config_rejects_non_input_entity(hass: HomeAssistant) -> None:
    errors = ManualProvider(hass, {"entity_id": "sensor.foo"}).validate_config()
    assert any("input_number" in e for e in errors)


def test_validate_config_rejects_unknown_value_type(hass: HomeAssistant) -> None:
    errors = ManualProvider(
        hass, {"entity_id": "input_number.x", "value_type": "blob"}
    ).validate_config()
    assert any("value_type" in e for e in errors)
