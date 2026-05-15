"""Tests for logical_day/manual.py (Section 7.3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.logical_day.manual import ManualStrategy


def _local_dt(d: date, hour: int = 8) -> datetime:
    return dt_util.start_of_local_day(d) + timedelta(hours=hour)


async def test_first_call_initializes_to_today_offset_zero(hass: HomeAssistant) -> None:
    s = ManualStrategy(hass, {})
    result = await s.get_logical_date(_local_dt(date(2026, 5, 15)))
    assert result == (date(2026, 5, 15), 0)


async def test_advance_day_moves_to_today_when_stale(hass: HomeAssistant) -> None:
    """Calendar moved on without advance_day → cal_offset grows."""
    s = ManualStrategy(hass, {})
    await s.get_logical_date(_local_dt(date(2026, 5, 15)))  # initialise
    result = await s.get_logical_date(_local_dt(date(2026, 5, 17)))
    assert result == (date(2026, 5, 15), 2)


async def test_advance_day_resets_offset_to_zero(hass: HomeAssistant) -> None:
    s = ManualStrategy(hass, {})
    await s.get_logical_date(_local_dt(date(2026, 5, 15)))
    new = s.advance_day(date(2026, 5, 17))
    assert new == date(2026, 5, 17)
    result = await s.get_logical_date(_local_dt(date(2026, 5, 17)))
    assert result == (date(2026, 5, 17), 0)


async def test_advance_day_never_goes_backward(hass: HomeAssistant) -> None:
    """advance_day(yesterday) is a no-op (max-keeps-the-latest)."""
    s = ManualStrategy(hass, {})
    await s.get_logical_date(_local_dt(date(2026, 5, 17)))
    new = s.advance_day(date(2026, 5, 10))
    assert new == date(2026, 5, 17)


def test_validate_config_always_empty(hass: HomeAssistant) -> None:
    assert ManualStrategy(hass, {}).validate_config() == []
    # Even with junk in config, manual has no schema params to police.
    assert ManualStrategy(hass, {"unrelated": "junk"}).validate_config() == []
