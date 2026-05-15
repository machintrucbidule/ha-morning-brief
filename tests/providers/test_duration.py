"""Tests for providers/duration.py (Section 8.5)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.providers.duration import DurationProvider


async def test_input_datetime_source_computes_days_elapsed(hass: HomeAssistant) -> None:
    target = date(2026, 5, 15)
    six_days_ago = dt_util.start_of_local_day(target - timedelta(days=6))
    eid = "input_datetime.litter_last_clean"
    hass.states.async_set(eid, six_days_ago.isoformat())

    cfg = {"source_type": "input_datetime", "entity_id": eid, "display_unit": "days"}
    result = await DurationProvider(hass, cfg).get_current_value(target)
    assert result.unit == "days"
    assert result.raw is not None
    assert 6.5 < float(result.raw) < 7.5  # ≈ 7 days at end-of-day


async def test_unavailable_reference_is_stale(hass: HomeAssistant) -> None:
    eid = "input_datetime.litter_last_clean"
    hass.states.async_set(eid, "unavailable")
    cfg = {"source_type": "input_datetime", "entity_id": eid, "display_unit": "days"}
    result = await DurationProvider(hass, cfg).get_current_value(date(2026, 5, 15))
    assert result.raw is None
    assert result.stale is True


async def test_future_reference_clamps_to_zero(hass: HomeAssistant) -> None:
    target = date(2026, 5, 15)
    future = dt_util.start_of_local_day(target + timedelta(days=10))
    eid = "input_datetime.future_event"
    hass.states.async_set(eid, future.isoformat())
    cfg = {"source_type": "input_datetime", "entity_id": eid, "display_unit": "hours"}
    result = await DurationProvider(hass, cfg).get_current_value(target)
    assert result.raw == 0.0


async def test_sensor_attribute_datetime_source(hass: HomeAssistant) -> None:
    target = date(2026, 5, 15)
    two_hours_ago = dt_util.start_of_local_day(target) + timedelta(hours=22)
    eid = "sensor.front_door"
    hass.states.async_set(eid, "open", {"opened_at": two_hours_ago.isoformat()})
    cfg = {
        "source_type": "sensor_attribute_datetime",
        "entity_id": eid,
        "attribute_name": "opened_at",
        "display_unit": "hours",
    }
    result = await DurationProvider(hass, cfg).get_current_value(target)
    assert result.unit == "hours"
    assert result.raw is not None
    assert 1.5 < float(result.raw) < 2.5


async def test_auto_unit_picks_days_for_long_durations(hass: HomeAssistant) -> None:
    target = date(2026, 5, 15)
    long_ago = dt_util.start_of_local_day(target - timedelta(days=30))
    eid = "input_datetime.x"
    hass.states.async_set(eid, long_ago.isoformat())
    cfg = {"source_type": "input_datetime", "entity_id": eid, "display_unit": "auto"}
    result = await DurationProvider(hass, cfg).get_current_value(target)
    assert result.unit == "days"


def test_validate_config_requires_attribute_name_for_attr_source(
    hass: HomeAssistant,
) -> None:
    errors = DurationProvider(
        hass,
        {
            "source_type": "sensor_attribute_datetime",
            "entity_id": "sensor.x",
            "display_unit": "auto",
        },
    ).validate_config()
    assert any("attribute_name" in e for e in errors)


def test_validate_config_rejects_unknown_source_type(hass: HomeAssistant) -> None:
    errors = DurationProvider(
        hass, {"source_type": "blob", "entity_id": "x"}
    ).validate_config()
    assert any("source_type" in e for e in errors)


def test_detect_from_entity_input_datetime(hass: HomeAssistant) -> None:
    assert DurationProvider.detect_from_entity(hass, "input_datetime.foo") == 0.7


# `datetime` and `timezone` reserved for future tz-conversion tests.
_ = datetime
_ = timezone
