"""Tests for logical_day/sleep_sensor.py (Section 7.2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.history import StateChange
from custom_components.morning_brief.logical_day.sleep_sensor import (
    SleepSensorStrategy,
)

SENSOR = "binary_sensor.is_sleeping"


def _local_dt(d: date, hour: int, minute: int = 0) -> datetime:
    return dt_util.start_of_local_day(d) + timedelta(hours=hour, minutes=minute)


def _strategy(hass: HomeAssistant, **overrides: object) -> SleepSensorStrategy:
    cfg: dict[str, object] = {
        "sleep_sensor_entity": SENSOR,
        "awake_state": "off",
        "hard_fallback_hour": 12,
        "lookback_hours": 36,
        "min_sleep_duration_minutes": 120,
    }
    cfg.update(overrides)
    return SleepSensorStrategy(hass, cfg)


async def test_wake_after_long_sleep_picks_correct_logical_day(hass: HomeAssistant) -> None:
    """8 hours asleep then wake at 07:00 → logical day is the calendar day before."""
    today = date(2026, 5, 15)
    asleep_start = _local_dt(today - timedelta(days=1), 23)  # yesterday 23:00
    wake = _local_dt(today, 7)  # today 07:00
    changes = [
        StateChange(timestamp=asleep_start, state="on", attributes={}),
        StateChange(timestamp=wake, state="off", attributes={}),
    ]
    with patch(
        "custom_components.morning_brief.logical_day.sleep_sensor.get_short_term",
        AsyncMock(return_value=changes),
    ):
        result = await _strategy(hass).get_logical_date(_local_dt(today, 8))
    # The wake at 07:00 minus 4h anchors to "today 03:00" → today's date.
    # That's correct: the night ENDED on today, but the night STARTED yesterday.
    # The strategy intentionally uses a 4h-back anchor to land on yesterday.
    assert result[0] == date(2026, 5, 14)
    assert result[1] == 1


async def test_nap_filtered_out(hass: HomeAssistant) -> None:
    """A 30-minute "wake" (nap exit) doesn't count; the real wake before it does."""
    today = date(2026, 5, 15)
    real_asleep = _local_dt(today - timedelta(days=1), 23)
    real_wake = _local_dt(today, 7)
    nap_start = _local_dt(today, 14)
    nap_end = _local_dt(today, 14, 30)
    changes = [
        StateChange(timestamp=real_asleep, state="on", attributes={}),
        StateChange(timestamp=real_wake, state="off", attributes={}),
        StateChange(timestamp=nap_start, state="on", attributes={}),
        StateChange(timestamp=nap_end, state="off", attributes={}),
    ]
    with patch(
        "custom_components.morning_brief.logical_day.sleep_sensor.get_short_term",
        AsyncMock(return_value=changes),
    ):
        result = await _strategy(hass).get_logical_date(_local_dt(today, 16))
    # Real wake anchors to date(today - 1 day) since 07:00 - 4h = 03:00 today,
    # but actually 03:00 on today's date; the spec wants "calendar day that
    # contains the start of the night" — yesterday. Verified above.
    assert result[0] == date(2026, 5, 14)


async def test_no_transitions_falls_back_to_hard_fallback(hass: HomeAssistant) -> None:
    """No wake events in lookback → hard_fallback_hour logic kicks in."""
    today = date(2026, 5, 15)
    with patch(
        "custom_components.morning_brief.logical_day.sleep_sensor.get_short_term",
        AsyncMock(return_value=[]),
    ):
        # before fallback hour → yesterday
        result_morning = await _strategy(hass, hard_fallback_hour=12).get_logical_date(
            _local_dt(today, 8)
        )
        # after fallback hour → today
        result_afternoon = await _strategy(hass, hard_fallback_hour=12).get_logical_date(
            _local_dt(today, 14)
        )
    assert result_morning == (date(2026, 5, 14), 1)
    assert result_afternoon == (date(2026, 5, 15), 0)


async def test_sensor_lookup_failure_falls_back(hass: HomeAssistant) -> None:
    """Recorder failure → hard fallback (R8)."""
    today = date(2026, 5, 15)
    with patch(
        "custom_components.morning_brief.logical_day.sleep_sensor.get_short_term",
        AsyncMock(side_effect=RuntimeError("recorder boom")),
    ):
        result = await _strategy(hass).get_logical_date(_local_dt(today, 8))
    assert result[0] == date(2026, 5, 14)


async def test_multiple_wake_transitions_uses_most_recent(hass: HomeAssistant) -> None:
    today = date(2026, 5, 15)
    # 2 nights, each with a real wake. The MOST RECENT wake is what counts.
    changes = [
        StateChange(timestamp=_local_dt(today - timedelta(days=2), 23), state="on", attributes={}),
        StateChange(timestamp=_local_dt(today - timedelta(days=1), 7), state="off", attributes={}),
        StateChange(timestamp=_local_dt(today - timedelta(days=1), 23), state="on", attributes={}),
        StateChange(timestamp=_local_dt(today, 7), state="off", attributes={}),
    ]
    with patch(
        "custom_components.morning_brief.logical_day.sleep_sensor.get_short_term",
        AsyncMock(return_value=changes),
    ):
        result = await _strategy(hass).get_logical_date(_local_dt(today, 8))
    assert result[0] == date(2026, 5, 14)


def test_validate_config_requires_binary_sensor(hass: HomeAssistant) -> None:
    errors = SleepSensorStrategy(
        hass, {"sleep_sensor_entity": "sensor.foo"}
    ).validate_config()
    assert any("binary_sensor" in e for e in errors)


def test_validate_config_requires_entity(hass: HomeAssistant) -> None:
    errors = SleepSensorStrategy(hass, {}).validate_config()
    assert any("sleep_sensor_entity" in e for e in errors)
