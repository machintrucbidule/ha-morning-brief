"""Tests for logical_day/fixed_cutoff.py (Section 7.1)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.logical_day.fixed_cutoff import (
    FixedCutoffStrategy,
)


def _local_dt(d: date, hour: int) -> datetime:
    return dt_util.start_of_local_day(d) + timedelta(hours=hour)


async def test_after_cutoff_returns_today_with_offset_zero(
    hass: HomeAssistant,
) -> None:
    s = FixedCutoffStrategy(hass, {"cutoff_hour": 4})
    now = _local_dt(date(2026, 5, 15), 7)
    logical_date, cal_offset = await s.get_logical_date(now)
    assert logical_date == date(2026, 5, 15)
    assert cal_offset == 0


async def test_before_cutoff_returns_yesterday_with_offset_one(
    hass: HomeAssistant,
) -> None:
    s = FixedCutoffStrategy(hass, {"cutoff_hour": 4})
    now = _local_dt(date(2026, 5, 15), 2)
    logical_date, cal_offset = await s.get_logical_date(now)
    assert logical_date == date(2026, 5, 14)
    assert cal_offset == 1


async def test_exact_cutoff_hour_is_today(hass: HomeAssistant) -> None:
    """At exactly cutoff_hour:00, we count as today."""
    s = FixedCutoffStrategy(hass, {"cutoff_hour": 4})
    now = _local_dt(date(2026, 5, 15), 4)
    logical_date, cal_offset = await s.get_logical_date(now)
    assert logical_date == date(2026, 5, 15)
    assert cal_offset == 0


async def test_default_cutoff_hour_is_4(hass: HomeAssistant) -> None:
    s = FixedCutoffStrategy(hass, {})
    assert s.cutoff_hour == 4


async def test_zero_cutoff_means_logical_equals_calendar(hass: HomeAssistant) -> None:
    """cutoff_hour=0 → logical_date is always the calendar date."""
    s = FixedCutoffStrategy(hass, {"cutoff_hour": 0})
    for hour in (0, 4, 12, 23):
        now = _local_dt(date(2026, 5, 15), hour)
        logical_date, cal_offset = await s.get_logical_date(now)
        assert logical_date == date(2026, 5, 15)
        assert cal_offset == 0


def test_validate_config_rejects_out_of_range_hour(hass: HomeAssistant) -> None:
    errors = FixedCutoffStrategy(hass, {"cutoff_hour": 24}).validate_config()
    assert any("cutoff_hour" in e for e in errors)


def test_validate_config_accepts_default(hass: HomeAssistant) -> None:
    assert FixedCutoffStrategy(hass, {}).validate_config() == []
