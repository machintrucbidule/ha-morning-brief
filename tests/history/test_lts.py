"""Tests for history/lts.py (Section 10.2 + 10.7)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.exceptions import HistoryError
from custom_components.morning_brief.history.lts import (
    _parse_bucket_start,
    entity_has_lts,
    get_lts_daily,
)

ENTITY = "sensor.test_sensor"


def _local_midnight(d: date) -> datetime:
    """Local-midnight datetime (UTC) for `d`."""
    return dt_util.start_of_local_day(d)


def _row(d: date, value: float, agg: str = "mean") -> dict[str, Any]:
    """Build one LTS row as `statistics_during_period` returns them."""
    return {"start": _local_midnight(d), agg: value}


async def test_entity_has_lts_true_when_state_class_present(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    assert entity_has_lts(hass, ENTITY) is True


async def test_entity_has_lts_false_without_state_class(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "1", {})
    assert entity_has_lts(hass, ENTITY) is False


async def test_entity_has_lts_false_when_entity_missing(hass: HomeAssistant) -> None:
    assert entity_has_lts(hass, "sensor.nope") is False


async def test_get_lts_daily_happy_path(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    """A clean 3-day window with one bucket per day."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    start, end = date(2026, 5, 10), date(2026, 5, 12)
    rows = {
        ENTITY: [
            _row(date(2026, 5, 10), 10.0),
            _row(date(2026, 5, 11), 20.0),
            _row(date(2026, 5, 12), 30.0),
        ]
    }
    with (
        patch(
            "custom_components.morning_brief.history.lts.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.lts.statistics.statistics_during_period",
            return_value=rows,
        ),
    ):
        result = await get_lts_daily(hass, ENTITY, start, end, "mean")
    assert result == {
        date(2026, 5, 10): 10.0,
        date(2026, 5, 11): 20.0,
        date(2026, 5, 12): 30.0,
    }


async def test_get_lts_daily_with_gap_in_middle(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    """Missing buckets stay None in the returned dict (G3)."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    start, end = date(2026, 5, 10), date(2026, 5, 12)
    rows = {
        ENTITY: [
            _row(date(2026, 5, 10), 10.0),
            # 2026-05-11 missing
            _row(date(2026, 5, 12), 30.0),
        ]
    }
    with (
        patch(
            "custom_components.morning_brief.history.lts.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.lts.statistics.statistics_during_period",
            return_value=rows,
        ),
    ):
        result = await get_lts_daily(hass, ENTITY, start, end, "mean")
    assert result[date(2026, 5, 10)] == 10.0
    assert result[date(2026, 5, 11)] is None
    assert result[date(2026, 5, 12)] == 30.0


async def test_get_lts_daily_raises_when_entity_has_no_state_class(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ENTITY, "1", {})
    with pytest.raises(HistoryError, match="no LTS"):
        await get_lts_daily(hass, ENTITY, date(2026, 5, 10), date(2026, 5, 12), "mean")


async def test_get_lts_daily_raises_on_unsupported_aggregation(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    with pytest.raises(HistoryError, match="Unsupported LTS aggregation"):
        await get_lts_daily(hass, ENTITY, date(2026, 5, 10), date(2026, 5, 12), "last")


async def test_get_lts_daily_raises_on_reversed_range(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    with pytest.raises(HistoryError, match="before"):
        await get_lts_daily(hass, ENTITY, date(2026, 5, 12), date(2026, 5, 10), "mean")


async def test_get_lts_daily_wraps_recorder_failure(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    """A recorder exception becomes a HistoryError."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    with (
        patch(
            "custom_components.morning_brief.history.lts.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.lts.statistics.statistics_during_period",
            side_effect=RuntimeError("recorder boom"),
        ),
        pytest.raises(HistoryError, match="LTS query failed"),
    ):
        await get_lts_daily(
            hass, ENTITY, date(2026, 5, 10), date(2026, 5, 12), "mean"
        )


async def test_get_lts_daily_handles_empty_result(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    """Entity exists with state_class but recorder returns nothing."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    start, end = date(2026, 5, 10), date(2026, 5, 11)
    with (
        patch(
            "custom_components.morning_brief.history.lts.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.lts.statistics.statistics_during_period",
            return_value={},
        ),
    ):
        result = await get_lts_daily(hass, ENTITY, start, end, "mean")
    assert result == {date(2026, 5, 10): None, date(2026, 5, 11): None}


def test_parse_bucket_start_accepts_datetime() -> None:
    dt = dt_util.start_of_local_day(date(2026, 5, 10))
    assert _parse_bucket_start(dt) == date(2026, 5, 10)


def test_parse_bucket_start_accepts_timestamp_float() -> None:
    dt = dt_util.start_of_local_day(date(2026, 5, 10))
    assert _parse_bucket_start(dt.timestamp()) == date(2026, 5, 10)


def test_parse_bucket_start_returns_none_for_garbage() -> None:
    assert _parse_bucket_start("not a date") is None
    assert _parse_bucket_start(None) is None
