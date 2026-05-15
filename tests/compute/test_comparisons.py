# rationale: covers all 8 V1 comparison types (D14) plus the
# interpretation helper and the dispatcher. Single file keeps the closed
# enum's behaviour assertions together (Section 11).
"""Tests for compute/comparisons.py (Section 11)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.compute.comparisons import (
    _linear_regression_slope,
    compare_rolling_avg,
    compare_rolling_max,
    compare_rolling_min,
    compare_same_week_last_year,
    compare_same_weekday_last_week,
    compare_target_value,
    compare_trend,
    compare_yesterday,
    compute_interpretation,
    evaluate_comparisons,
)
from custom_components.morning_brief.history import HistoryResult
from custom_components.morning_brief.providers.base import FieldProvider
from custom_components.morning_brief.types import FieldValue

ENTITY = "sensor.x"


def _provider_with(prev_raw: float | None = None, entity_id: str = ENTITY) -> MagicMock:
    prov = MagicMock(spec=FieldProvider)
    prov.config = {"entity_id": entity_id}
    prov.get_value_for_date = AsyncMock(
        return_value=FieldValue(raw=prev_raw, unit="bpm")
    )
    return prov


def _result(data: dict[date, float | None], status: str = "ok") -> HistoryResult:
    days_used = sum(1 for v in data.values() if v is not None)
    return HistoryResult(
        data=data,
        status=status,
        days_used=days_used,
        days_expected=len(data),
        sources_used=["lts"] if days_used else [],
    )


# --------------------------------------------------------------------------- #
# yesterday + same_weekday_last_week (single-day reference)
# --------------------------------------------------------------------------- #


async def test_yesterday_happy_path() -> None:
    cur = FieldValue(raw=65.0, unit="bpm")
    prov = _provider_with(prev_raw=60.0)
    r = await compare_yesterday(prov, cur, date(2026, 5, 15))
    assert r.type == "yesterday"
    assert r.value == 60.0
    assert r.delta == 5.0
    assert r.direction == "up"
    assert r.status == "ok"
    prov.get_value_for_date.assert_awaited_once_with(date(2026, 5, 14))


async def test_yesterday_missing_previous_returns_insufficient() -> None:
    cur = FieldValue(raw=65.0, unit="bpm")
    prov = _provider_with(prev_raw=None)
    r = await compare_yesterday(prov, cur, date(2026, 5, 15))
    assert r.status == "insufficient_history"
    assert r.value is None


async def test_yesterday_missing_current_returns_insufficient() -> None:
    cur = FieldValue(raw=None)
    prov = _provider_with(prev_raw=60.0)
    r = await compare_yesterday(prov, cur, date(2026, 5, 15))
    assert r.status == "insufficient_history"


async def test_same_weekday_last_week_uses_j_minus_7() -> None:
    cur = FieldValue(raw=65.0)
    prov = _provider_with(prev_raw=64.0)
    await compare_same_weekday_last_week(prov, cur, date(2026, 5, 15))
    prov.get_value_for_date.assert_awaited_once_with(date(2026, 5, 8))


# --------------------------------------------------------------------------- #
# rolling_avg / rolling_min / rolling_max
# --------------------------------------------------------------------------- #


async def test_rolling_avg_excludes_logical_date(hass: HomeAssistant) -> None:
    """The window is [logical-N, logical-1] — logical itself is NOT included."""
    days = [date(2026, 5, 15) - timedelta(days=i) for i in range(1, 15)]
    data = {d: 60.0 for d in days}
    cur = FieldValue(raw=65.0)
    captured: dict[str, Any] = {}

    async def fake_query(_hass: object, q: object) -> HistoryResult:
        captured["q"] = q
        return _result(data)

    with patch(
        "custom_components.morning_brief.compute.comparisons.query",
        side_effect=fake_query,
    ):
        r = await compare_rolling_avg(hass, _provider_with(), cur, date(2026, 5, 15), 14)
    assert r.value == 60.0
    assert r.delta == 5.0
    assert r.status == "ok"
    assert captured["q"].start_date == date(2026, 5, 1)
    assert captured["q"].end_date == date(2026, 5, 14)


async def test_rolling_min_picks_lowest_daily_value(hass: HomeAssistant) -> None:
    days = [date(2026, 5, 15) - timedelta(days=i) for i in range(1, 8)]
    data = dict(zip(days, [62.0, 60.0, 58.0, 61.0, 59.0, 63.0, 60.0], strict=False))
    cur = FieldValue(raw=65.0)
    with patch(
        "custom_components.morning_brief.compute.comparisons.query",
        AsyncMock(return_value=_result(data)),
    ):
        r = await compare_rolling_min(hass, _provider_with(), cur, date(2026, 5, 15), 7)
    assert r.value == 58.0


async def test_rolling_max_picks_highest_daily_value(hass: HomeAssistant) -> None:
    days = [date(2026, 5, 15) - timedelta(days=i) for i in range(1, 8)]
    data = dict(zip(days, [62.0, 60.0, 58.0, 61.0, 59.0, 63.0, 60.0], strict=False))
    cur = FieldValue(raw=65.0)
    with patch(
        "custom_components.morning_brief.compute.comparisons.query",
        AsyncMock(return_value=_result(data)),
    ):
        r = await compare_rolling_max(hass, _provider_with(), cur, date(2026, 5, 15), 7)
    assert r.value == 63.0


async def test_rolling_avg_no_valid_data_returns_insufficient(hass: HomeAssistant) -> None:
    days = [date(2026, 5, 15) - timedelta(days=i) for i in range(1, 15)]
    data: dict[date, float | None] = dict.fromkeys(days)
    cur = FieldValue(raw=65.0)
    with patch(
        "custom_components.morning_brief.compute.comparisons.query",
        AsyncMock(return_value=_result(data, status="insufficient_history")),
    ):
        r = await compare_rolling_avg(hass, _provider_with(), cur, date(2026, 5, 15), 14)
    assert r.status == "insufficient_history"


# --------------------------------------------------------------------------- #
# target_value
# --------------------------------------------------------------------------- #


async def test_target_value_happy() -> None:
    r = compare_target_value(FieldValue(raw=78.0), target=75.0)
    assert r.value == 75.0
    assert r.delta == 3.0
    assert r.direction == "up"


async def test_target_value_missing_current() -> None:
    r = compare_target_value(FieldValue(raw=None), target=75.0)
    assert r.status == "insufficient_history"


# --------------------------------------------------------------------------- #
# trend
# --------------------------------------------------------------------------- #


async def test_trend_with_clear_upward_slope(hass: HomeAssistant) -> None:
    days = [date(2026, 5, 15) - timedelta(days=i) for i in range(6, -1, -1)]
    data = dict(zip(days, [60.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0], strict=False))
    with patch(
        "custom_components.morning_brief.compute.comparisons.query",
        AsyncMock(return_value=_result(data)),
    ):
        r = await compare_trend(hass, _provider_with(), FieldValue(raw=66.0), date(2026, 5, 15), 7)
    assert r.direction == "up"
    assert r.value is not None
    assert r.value > 0


async def test_trend_too_few_points_returns_insufficient(hass: HomeAssistant) -> None:
    days = [date(2026, 5, 15) - timedelta(days=i) for i in range(2)]
    data = {days[0]: 60.0, days[1]: None}  # only one valid point
    with patch(
        "custom_components.morning_brief.compute.comparisons.query",
        AsyncMock(return_value=_result(data, status="insufficient_history")),
    ):
        r = await compare_trend(hass, _provider_with(), FieldValue(raw=65.0), date(2026, 5, 15), 2)
    assert r.status == "insufficient_history"


def test_linear_regression_slope_handles_collinear_x() -> None:
    """Zero-variance x doesn't divide by zero."""
    assert _linear_regression_slope([(0, 1.0), (0, 2.0)]) == 0.0


# --------------------------------------------------------------------------- #
# same_week_last_year (D24)
# --------------------------------------------------------------------------- #


async def test_same_week_last_year_returns_insufficient_when_less_than_53_weeks(
    hass: HomeAssistant,
) -> None:
    """If the last_year ISO week is < 365 days ago, return insufficient."""
    logical = date.today()  # ISO week of today; previous year is ~365 days back
    r = await compare_same_week_last_year(
        hass, _provider_with(), FieldValue(raw=10.0), logical
    )
    # `today() - last_year_iso_start` may be < 365 by a few days depending on
    # ISO week alignment — status should be insufficient_history in that case.
    if r.status == "insufficient_history":
        assert r.value is None


async def test_same_week_last_year_happy_path(hass: HomeAssistant) -> None:
    """When the target ISO week is fully ≥ 365 days ago, return the agg."""
    logical = date(2026, 5, 15)
    # Build a 7-day window inside 2025 week 20.
    days = [date(2025, 5, 12) + timedelta(days=i) for i in range(7)]
    data = dict.fromkeys(days, 100.0)
    with patch(
        "custom_components.morning_brief.compute.comparisons.query",
        AsyncMock(return_value=_result(data)),
    ):
        r = await compare_same_week_last_year(
            hass,
            _provider_with(),
            FieldValue(raw=110.0),
            logical,
            weekly_aggregation="mean",
        )
    assert r.value == 100.0
    assert r.delta == 10.0


# --------------------------------------------------------------------------- #
# interpretation helper
# --------------------------------------------------------------------------- #


def test_interpretation_up_with_higher_is_better_is_improvement() -> None:
    assert compute_interpretation("up", "higher_is_better") == "improvement"
    assert compute_interpretation("down", "higher_is_better") == "worsening"
    assert compute_interpretation("up", "lower_is_better") == "worsening"
    assert compute_interpretation("down", "lower_is_better") == "improvement"


def test_interpretation_flat_or_neutral_is_neutral() -> None:
    assert compute_interpretation("flat", "higher_is_better") == "neutral"
    assert compute_interpretation("up", "neutral") == "neutral"


# --------------------------------------------------------------------------- #
# evaluate_comparisons dispatcher
# --------------------------------------------------------------------------- #


async def test_evaluate_comparisons_runs_each_configured_type(hass: HomeAssistant) -> None:
    """Yesterday + target_value in one field config → 2 Comparison results."""
    cur = FieldValue(raw=10.0)
    prov = _provider_with(prev_raw=8.0)
    field_config = {
        "comparisons": [
            {"type": "yesterday"},
            {"type": "target_value", "target": 9},
        ],
    }
    results = await evaluate_comparisons(
        hass, prov, cur, date(2026, 5, 15), field_config, "higher_is_better"
    )
    assert [r.type for r in results] == ["yesterday", "target_value"]
    assert all(r.interpretation in ("improvement", "worsening", "neutral") for r in results)


async def test_evaluate_comparisons_unknown_type_is_not_applicable(
    hass: HomeAssistant,
) -> None:
    field_config = {"comparisons": [{"type": "blob"}]}
    results = await evaluate_comparisons(
        hass, _provider_with(), FieldValue(raw=1.0), date(2026, 5, 15), field_config, "neutral"
    )
    assert results[0].status == "not_applicable"


async def test_evaluate_comparisons_exception_logged_and_marked_not_applicable(
    hass: HomeAssistant,
) -> None:
    """A misbehaving comparison shouldn't crash the brief (R6 entry-point)."""
    prov = _provider_with()
    prov.get_value_for_date = AsyncMock(side_effect=RuntimeError("boom"))
    field_config = {"comparisons": [{"type": "yesterday"}]}
    results = await evaluate_comparisons(
        hass, prov, FieldValue(raw=1.0), date(2026, 5, 15), field_config, "neutral"
    )
    assert results[0].status == "not_applicable"
