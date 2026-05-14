"""Tests for history/short_term.py (Section 10.3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.exceptions import HistoryError
from custom_components.morning_brief.history.short_term import (
    StateChange,
    _aggregate,
    _coerce_float,
    get_short_term,
    get_short_term_daily_aggregate,
)

ENTITY = "sensor.test_sensor"


def _fake_state(state: str, ts: datetime, attrs: dict[str, Any] | None = None) -> SimpleNamespace:
    """A duck-typed `State` object as `state_changes_during_period` returns."""
    return SimpleNamespace(state=state, last_changed=ts, attributes=attrs or {})


def _local_dt(d: date, hour: int = 12) -> datetime:
    """A local datetime on day `d` at `hour:00`."""
    return dt_util.start_of_local_day(d) + timedelta(hours=hour)


async def test_get_short_term_returns_sorted_state_changes(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    d = date(2026, 5, 10)
    t1, t2, t3 = _local_dt(d, 1), _local_dt(d, 5), _local_dt(d, 10)
    states = [_fake_state("3", t3), _fake_state("1", t1), _fake_state("2", t2)]
    with (
        patch(
            "custom_components.morning_brief.history.short_term.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.short_term.recorder_history.state_changes_during_period",
            return_value={ENTITY: states},
        ),
    ):
        out = await get_short_term(hass, ENTITY, t1, t3 + timedelta(hours=1))
    assert [c.timestamp for c in out] == [t1, t2, t3]
    assert [c.state for c in out] == ["1", "2", "3"]


async def test_get_short_term_empty_when_entity_absent(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    """Recorder returns nothing for the entity → empty list, no error."""
    with (
        patch(
            "custom_components.morning_brief.history.short_term.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.short_term.recorder_history.state_changes_during_period",
            return_value={},
        ),
    ):
        out = await get_short_term(
            hass, ENTITY, _local_dt(date(2026, 5, 10)), _local_dt(date(2026, 5, 11))
        )
    assert out == []


async def test_get_short_term_wraps_recorder_failure(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    with (
        patch(
            "custom_components.morning_brief.history.short_term.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.short_term.recorder_history.state_changes_during_period",
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(HistoryError, match="short-term query failed"),
    ):
        await get_short_term(
            hass, ENTITY, _local_dt(date(2026, 5, 10)), _local_dt(date(2026, 5, 11))
        )


async def test_daily_aggregate_mean_per_day(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    """Multiple numeric samples per day average correctly per local day."""
    d1, d2 = date(2026, 5, 10), date(2026, 5, 11)
    states = [
        _fake_state("10", _local_dt(d1, 8)),
        _fake_state("20", _local_dt(d1, 16)),
        _fake_state("50", _local_dt(d2, 12)),
    ]
    with (
        patch(
            "custom_components.morning_brief.history.short_term.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.short_term.recorder_history.state_changes_during_period",
            return_value={ENTITY: states},
        ),
    ):
        result = await get_short_term_daily_aggregate(hass, ENTITY, d1, d2, "mean")
    assert result == {d1: 15.0, d2: 50.0}


async def test_daily_aggregate_filters_unavailable(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    """`unavailable` / `unknown` are dropped before aggregation."""
    d1 = date(2026, 5, 10)
    states = [
        _fake_state("10", _local_dt(d1, 8)),
        _fake_state("unavailable", _local_dt(d1, 12)),
        _fake_state("unknown", _local_dt(d1, 14)),
        _fake_state("20", _local_dt(d1, 16)),
    ]
    with (
        patch(
            "custom_components.morning_brief.history.short_term.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.short_term.recorder_history.state_changes_during_period",
            return_value={ENTITY: states},
        ),
    ):
        result = await get_short_term_daily_aggregate(hass, ENTITY, d1, d1, "mean")
    assert result == {d1: 15.0}


async def test_daily_aggregate_none_for_days_without_data(
    hass: HomeAssistant, mock_recorder: MagicMock
) -> None:
    """Days with no valid numeric samples remain None in the output."""
    d1, d2, d3 = date(2026, 5, 10), date(2026, 5, 11), date(2026, 5, 12)
    states = [_fake_state("10", _local_dt(d1, 8))]
    with (
        patch(
            "custom_components.morning_brief.history.short_term.get_instance",
            return_value=mock_recorder,
        ),
        patch(
            "custom_components.morning_brief.history.short_term.recorder_history.state_changes_during_period",
            return_value={ENTITY: states},
        ),
    ):
        result = await get_short_term_daily_aggregate(hass, ENTITY, d1, d3, "mean")
    assert result == {d1: 10.0, d2: None, d3: None}


async def test_daily_aggregate_raises_on_reversed_range(hass: HomeAssistant) -> None:
    with pytest.raises(HistoryError, match="before"):
        await get_short_term_daily_aggregate(
            hass, ENTITY, date(2026, 5, 12), date(2026, 5, 10), "mean"
        )


def test_aggregate_supports_all_documented_modes() -> None:
    values = [1.0, 3.0, 5.0]
    assert _aggregate(values, "mean") == 3.0
    assert _aggregate(values, "sum") == 9.0
    assert _aggregate(values, "max") == 5.0
    assert _aggregate(values, "min") == 1.0
    assert _aggregate(values, "last") == 5.0


def test_aggregate_unknown_mode_raises() -> None:
    with pytest.raises(HistoryError, match="Unsupported"):
        _aggregate([1.0], "median")


def test_aggregate_empty_returns_none() -> None:
    assert _aggregate([], "mean") is None


def test_coerce_float_handles_invalid_inputs() -> None:
    assert _coerce_float("12.5") == 12.5
    assert _coerce_float("unavailable") is None
    assert _coerce_float("unknown") is None
    assert _coerce_float("") is None
    assert _coerce_float("not a number") is None


def test_state_change_is_frozen_dataclass() -> None:
    sc = StateChange(timestamp=_local_dt(date(2026, 5, 10)), state="1", attributes={})
    with pytest.raises((TypeError, AttributeError)):
        sc.state = "2"  # type: ignore[misc]
