# rationale: covers every scenario enumerated in MORNING_BRIEF_SPEC.md
# Section 10.7 (LTS-only, short-term-only, mixed, gaps, conflict resolution,
# all status enum values) plus retention-lookup edge cases (G7). Splitting
# would scatter related orchestration assertions across files.
"""Tests for history/hybrid.py (Section 10.5–10.7 + D10 + D11)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.exceptions import HistoryError
from custom_components.morning_brief.history.hybrid import (
    HistoryQuery,
    get_recorder_retention,
    query,
)

ENTITY = "sensor.test_sensor"


def _q(start: date, end: date, aggregation: str = "mean") -> HistoryQuery:
    return HistoryQuery(entity_id=ENTITY, start_date=start, end_date=end, aggregation=aggregation)


def _fixed_now() -> datetime:
    """A fixed local "now" so retention math is deterministic in tests."""
    return dt_util.start_of_local_day(date(2026, 5, 15)) + timedelta(hours=12)


async def test_lts_only_full_window_status_ok(hass: HomeAssistant) -> None:
    """LTS covers the entire window → status=ok, sources=['lts']."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    lts_data = {
        date(2026, 5, 10): 10.0,
        date(2026, 5, 11): 20.0,
        date(2026, 5, 12): 30.0,
    }
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_lts_daily",
            AsyncMock(return_value=lts_data),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(),
        ) as st_mock,
    ):
        result = await query(hass, _q(date(2026, 5, 10), date(2026, 5, 12)))
    assert result.status == "ok"
    assert result.days_used == 3
    assert result.days_expected == 3
    assert result.sources_used == ["lts"]
    assert result.data == lts_data
    # No need to fall through to short-term once LTS filled everything.
    st_mock.assert_not_called()


async def test_short_term_only_when_no_state_class(hass: HomeAssistant) -> None:
    """Entity has no state_class → skip LTS, go straight to short-term."""
    hass.states.async_set(ENTITY, "1", {})  # no state_class
    st_data = {
        date(2026, 5, 10): 10.0,
        date(2026, 5, 11): 20.0,
    }
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(return_value=st_data),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=30,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        result = await query(hass, _q(date(2026, 5, 10), date(2026, 5, 11)))
    assert result.status == "ok"
    assert result.sources_used == ["short_term"]
    assert result.data == st_data


async def test_mixed_lts_for_older_and_short_term_for_recent(hass: HomeAssistant) -> None:
    """LTS fills old dates, short-term fills the tail — sources lists both."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    lts_data = {
        date(2026, 5, 10): 10.0,
        date(2026, 5, 11): 20.0,
        date(2026, 5, 12): None,  # gap
    }
    st_data = {
        date(2026, 5, 10): None,
        date(2026, 5, 11): None,
        date(2026, 5, 12): 30.0,
    }
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_lts_daily",
            AsyncMock(return_value=lts_data),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(return_value=st_data),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=30,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        result = await query(hass, _q(date(2026, 5, 10), date(2026, 5, 12)))
    assert result.status == "ok"
    assert result.sources_used == ["lts", "short_term"]
    assert result.data == {
        date(2026, 5, 10): 10.0,
        date(2026, 5, 11): 20.0,
        date(2026, 5, 12): 30.0,
    }


async def test_lts_wins_on_conflict(hass: HomeAssistant) -> None:
    """Same date in both LTS and short-term → LTS value kept (D10)."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    lts_data = {date(2026, 5, 10): 10.0}
    st_data = {date(2026, 5, 10): 99.0}  # conflict — must be ignored
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_lts_daily",
            AsyncMock(return_value=lts_data),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(return_value=st_data),
        ) as st_mock,
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=30,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        result = await query(hass, _q(date(2026, 5, 10), date(2026, 5, 10)))
    assert result.data == {date(2026, 5, 10): 10.0}
    # short-term wasn't even consulted since LTS already filled everything.
    st_mock.assert_not_called()


async def test_partial_status_when_under_30pct_missing(hass: HomeAssistant) -> None:
    """One missing day out of 10 (10%) → status=partial."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    days = [date(2026, 5, 1) + timedelta(days=i) for i in range(10)]
    lts_data = {d: float(i) for i, d in enumerate(days)}
    lts_data[days[4]] = None  # one gap
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_lts_daily",
            AsyncMock(return_value=lts_data),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(return_value={d: None for d in days}),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=30,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        result = await query(hass, _q(days[0], days[-1]))
    assert result.status == "partial"
    assert result.days_used == 9
    assert result.days_expected == 10


async def test_unreliable_when_30pct_or_more_missing(hass: HomeAssistant) -> None:
    """Three missing days out of 10 (30%) → status=unreliable."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    days = [date(2026, 5, 1) + timedelta(days=i) for i in range(10)]
    lts_data = {d: float(i) for i, d in enumerate(days)}
    for d in (days[3], days[5], days[7]):
        lts_data[d] = None
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_lts_daily",
            AsyncMock(return_value=lts_data),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(return_value={d: None for d in days}),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=30,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        result = await query(hass, _q(days[0], days[-1]))
    assert result.status == "unreliable"
    assert result.days_used == 7


async def test_insufficient_history_when_no_data_anywhere(hass: HomeAssistant) -> None:
    """No usable values from any source → status=insufficient_history."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    days = [date(2026, 5, 10) + timedelta(days=i) for i in range(3)]
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_lts_daily",
            AsyncMock(return_value={d: None for d in days}),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(return_value={d: None for d in days}),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=30,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        result = await query(hass, _q(days[0], days[-1]))
    assert result.status == "insufficient_history"
    assert result.days_used == 0


async def test_lts_failure_falls_back_to_short_term(hass: HomeAssistant) -> None:
    """If LTS raises HistoryError, short-term should still be tried."""
    hass.states.async_set(ENTITY, "1", {"state_class": "measurement"})
    st_data = {date(2026, 5, 10): 10.0}
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_lts_daily",
            AsyncMock(side_effect=HistoryError("boom")),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(return_value=st_data),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=30,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        result = await query(hass, _q(date(2026, 5, 10), date(2026, 5, 10)))
    assert result.data == st_data
    assert result.sources_used == ["short_term"]


async def test_short_term_window_bounded_by_recorder_retention(hass: HomeAssistant) -> None:
    """Short-term is only queried for the range the recorder still holds (G7).

    We ask for 30 days but recorder keeps only 5 — short-term call must
    receive a clamped `start_date`.
    """
    hass.states.async_set(ENTITY, "1", {})  # no state_class → straight to short-term
    today = _fixed_now().date()
    st_call_args: dict[str, object] = {}

    async def fake_st(
        _h: object,
        _e: object,
        start: date,
        end: date,
        _agg: object,
    ) -> dict[date, float | None]:
        st_call_args["start"] = start
        st_call_args["end"] = end
        return {start: 1.0}

    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            new=fake_st,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=5,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        await query(hass, _q(today - timedelta(days=30), today))
    # Short-term call clamped to recorder retention.
    assert st_call_args["start"] == today - timedelta(days=5)
    assert st_call_args["end"] == today


def test_get_recorder_retention_returns_recorder_value(hass: HomeAssistant) -> None:
    fake_recorder = MagicMock()
    fake_recorder.keep_days = 42
    with patch(
        "custom_components.morning_brief.history.hybrid.get_instance",
        return_value=fake_recorder,
    ):
        assert get_recorder_retention(hass) == 42


def test_get_recorder_retention_falls_back_when_attribute_missing(
    hass: HomeAssistant,
) -> None:
    fake_recorder = MagicMock(spec=[])  # no keep_days / purge_keep_days
    with patch(
        "custom_components.morning_brief.history.hybrid.get_instance",
        return_value=fake_recorder,
    ):
        # Default per DEFAULT_RECORDER_RETENTION_DAYS = 10 (G7 fallback).
        assert get_recorder_retention(hass) == 10


def test_get_recorder_retention_falls_back_when_get_instance_raises(
    hass: HomeAssistant,
) -> None:
    with patch(
        "custom_components.morning_brief.history.hybrid.get_instance",
        side_effect=RuntimeError("no recorder"),
    ):
        assert get_recorder_retention(hass) == 10


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 5, 10), date(2026, 5, 10)),
        (date(2026, 5, 10), date(2026, 5, 14)),
    ],
)
async def test_query_window_dict_always_covers_full_range(
    hass: HomeAssistant, start: date, end: date
) -> None:
    """Even when both sources return nothing, every requested date is keyed."""
    hass.states.async_set(ENTITY, "1", {})
    with (
        patch(
            "custom_components.morning_brief.history.hybrid.get_short_term_daily_aggregate",
            AsyncMock(return_value={}),
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.get_recorder_retention",
            return_value=30,
        ),
        patch(
            "custom_components.morning_brief.history.hybrid.dt_util.now",
            return_value=_fixed_now(),
        ),
    ):
        result = await query(hass, _q(start, end))
    expected_days = (end - start).days + 1
    assert len(result.data) == expected_days
    assert result.days_expected == expected_days
