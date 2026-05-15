# rationale: implements all 8 V1 comparison types (D14) in one file plus
# the dispatcher and the interpretation helper. Each type is tight (<25
# lines) and they share parameter shapes and status mapping — splitting
# would scatter the closed enum (Section 11).
"""Comparison computations (Section 11, D14).

Each comparison function takes a provider, the current FieldValue, the
logical date, plus type-specific parameters, and returns a
:class:`types.Comparison`. The dispatcher ``evaluate_comparisons`` walks
the field's configured comparisons in order.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from ..const import (
    COMPARISON_ROLLING_AVG,
    COMPARISON_ROLLING_MAX,
    COMPARISON_ROLLING_MIN,
    COMPARISON_SAME_WEEK_LAST_YEAR,
    COMPARISON_SAME_WEEKDAY_LAST_WEEK,
    COMPARISON_TARGET_VALUE,
    COMPARISON_TREND,
    COMPARISON_YESTERDAY,
    DIRECTION_HIGHER_IS_BETTER,
    DIRECTION_LOWER_IS_BETTER,
    HISTORY_AGG_MAX,
    HISTORY_AGG_MEAN,
    HISTORY_AGG_MIN,
    STATUS_INSUFFICIENT_HISTORY,
    STATUS_NOT_APPLICABLE,
    STATUS_OK,
)
from ..history import HistoryQuery, query
from ..providers.base import FieldProvider
from ..types import Comparison, FieldValue

_LOGGER = logging.getLogger(__name__)

# Float comparisons within this delta count as "flat" — protects against
# tiny noise in numeric sensors.
_FLAT_EPSILON = 1e-9


def _direction(delta: float) -> str:
    if delta > _FLAT_EPSILON:
        return "up"
    if delta < -_FLAT_EPSILON:
        return "down"
    return "flat"


def compute_interpretation(direction: str, direction_preference: str) -> str:
    """Map (direction, direction_preference) → improvement/worsening/neutral."""
    if direction == "flat" or direction_preference not in (
        DIRECTION_HIGHER_IS_BETTER,
        DIRECTION_LOWER_IS_BETTER,
    ):
        return "neutral"
    if direction == "up" and direction_preference == DIRECTION_HIGHER_IS_BETTER:
        return "improvement"
    if direction == "down" and direction_preference == DIRECTION_LOWER_IS_BETTER:
        return "improvement"
    return "worsening"


def _to_number(raw: Any) -> float | None:
    """Coerce a raw value to float — None on failure."""
    if isinstance(raw, int | float):
        return float(raw)
    return None


def _empty(type_: str, status: str, window_days: int | None = None) -> Comparison:
    return Comparison(type=type_, window_days=window_days, status=status)


async def _compare_to_single_day(
    type_: str,
    provider: FieldProvider,
    current_value: FieldValue,
    target_date: date,
) -> Comparison:
    prev = await provider.get_value_for_date(target_date)
    prev_num = _to_number(prev.raw)
    cur_num = _to_number(current_value.raw)
    if prev_num is None or cur_num is None:
        return _empty(type_, STATUS_INSUFFICIENT_HISTORY)
    delta = cur_num - prev_num
    return Comparison(
        type=type_,
        value=prev_num,
        delta=delta,
        direction=_direction(delta),
        status=STATUS_OK,
    )


async def compare_yesterday(
    provider: FieldProvider, current_value: FieldValue, logical_date: date
) -> Comparison:
    """J-1 comparison."""
    return await _compare_to_single_day(
        COMPARISON_YESTERDAY,
        provider,
        current_value,
        logical_date - timedelta(days=1),
    )


async def compare_same_weekday_last_week(
    provider: FieldProvider, current_value: FieldValue, logical_date: date
) -> Comparison:
    """J-7 comparison — same weekday a week earlier."""
    return await _compare_to_single_day(
        COMPARISON_SAME_WEEKDAY_LAST_WEEK,
        provider,
        current_value,
        logical_date - timedelta(days=7),
    )


async def _rolling(
    type_: str,
    hass: HomeAssistant,
    provider: FieldProvider,
    current_value: FieldValue,
    logical_date: date,
    window_days: int,
    aggregation: str,
    reducer: Any,
) -> Comparison:
    """Shared logic for rolling_{avg,min,max}.

    Queries LTS over the window EXCLUDING logical_date itself, then applies
    ``reducer`` (e.g. mean / min / max) to the non-None values.
    """
    cur_num = _to_number(current_value.raw)
    if cur_num is None:
        return _empty(type_, STATUS_INSUFFICIENT_HISTORY, window_days=window_days)

    start = logical_date - timedelta(days=window_days)
    end = logical_date - timedelta(days=1)
    result = await query(
        hass,
        HistoryQuery(
            entity_id=provider.config["entity_id"],
            start_date=start,
            end_date=end,
            aggregation=aggregation,
        ),
    )
    valid = [v for v in result.data.values() if v is not None]
    if not valid:
        return _empty(type_, STATUS_INSUFFICIENT_HISTORY, window_days=window_days)

    agg = reducer(valid)
    delta = cur_num - agg
    return Comparison(
        type=type_,
        window_days=window_days,
        value=agg,
        delta=delta,
        direction=_direction(delta),
        status=result.status,
        days_used=result.days_used,
    )


async def compare_rolling_avg(
    hass: HomeAssistant,
    provider: FieldProvider,
    current_value: FieldValue,
    logical_date: date,
    window_days: int,
) -> Comparison:
    return await _rolling(
        COMPARISON_ROLLING_AVG,
        hass,
        provider,
        current_value,
        logical_date,
        window_days,
        HISTORY_AGG_MEAN,
        lambda vs: sum(vs) / len(vs),
    )


async def compare_rolling_min(
    hass: HomeAssistant,
    provider: FieldProvider,
    current_value: FieldValue,
    logical_date: date,
    window_days: int,
) -> Comparison:
    return await _rolling(
        COMPARISON_ROLLING_MIN,
        hass,
        provider,
        current_value,
        logical_date,
        window_days,
        HISTORY_AGG_MIN,
        min,
    )


async def compare_rolling_max(
    hass: HomeAssistant,
    provider: FieldProvider,
    current_value: FieldValue,
    logical_date: date,
    window_days: int,
) -> Comparison:
    return await _rolling(
        COMPARISON_ROLLING_MAX,
        hass,
        provider,
        current_value,
        logical_date,
        window_days,
        HISTORY_AGG_MAX,
        max,
    )


def compare_target_value(current_value: FieldValue, target: float) -> Comparison:
    """Compare against a fixed numeric target."""
    cur_num = _to_number(current_value.raw)
    if cur_num is None:
        return _empty(COMPARISON_TARGET_VALUE, STATUS_INSUFFICIENT_HISTORY)
    delta = cur_num - target
    return Comparison(
        type=COMPARISON_TARGET_VALUE,
        value=target,
        delta=delta,
        direction=_direction(delta),
        status=STATUS_OK,
    )


def _linear_regression_slope(points: list[tuple[int, float]]) -> float:
    """Least-squares slope; assumes ``len(points) >= 2``."""
    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_xx = sum(p[0] * p[0] for p in points)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


async def compare_trend(
    hass: HomeAssistant,
    provider: FieldProvider,
    current_value: FieldValue,
    logical_date: date,
    window_days: int,
) -> Comparison:
    """Linear regression slope over the window. Need ≥ 3 points."""
    start = logical_date - timedelta(days=window_days)
    result = await query(
        hass,
        HistoryQuery(
            entity_id=provider.config["entity_id"],
            start_date=start,
            end_date=logical_date,
            aggregation=HISTORY_AGG_MEAN,
        ),
    )
    points = [
        (i, v)
        for i, (_, v) in enumerate(sorted(result.data.items()))
        if v is not None
    ]
    if len(points) < 3:
        return _empty(COMPARISON_TREND, STATUS_INSUFFICIENT_HISTORY, window_days=window_days)
    slope = _linear_regression_slope(points)
    return Comparison(
        type=COMPARISON_TREND,
        window_days=window_days,
        value=slope,
        direction=_direction(slope),
        status=result.status,
        days_used=result.days_used,
    )


_WeeklyReducer = Callable[[list[float]], float]
_WEEKLY_AGG_REDUCERS: dict[str, _WeeklyReducer] = {
    "sum": lambda vs: float(sum(vs)),
    "mean": lambda vs: sum(vs) / len(vs),
    "max": lambda vs: float(max(vs)),
    "min": lambda vs: float(min(vs)),
    "latest": lambda vs: vs[-1],
}


async def compare_same_week_last_year(
    hass: HomeAssistant,
    provider: FieldProvider,
    current_value: FieldValue,
    logical_date: date,
    weekly_aggregation: str = "mean",
) -> Comparison:
    """Aggregate value of the same ISO week one year earlier (D24).

    Returns ``insufficient_history`` when the recorder has fewer than ~53
    weeks of data (the gap is measured against today: if the target ISO
    week is < 365 days ago, we can't be sure LTS covers it).
    """
    iso = logical_date.isocalendar()
    # `iso.week` typed as int by stdlib; some HA versions wrap differently.
    week = int(iso[1] if isinstance(iso, tuple) else iso.week)
    year = int(iso[0] if isinstance(iso, tuple) else iso.year)
    try:
        last_year_start = date.fromisocalendar(year - 1, week, 1)
    except ValueError:
        return _empty(COMPARISON_SAME_WEEK_LAST_YEAR, STATUS_INSUFFICIENT_HISTORY)
    last_year_end = last_year_start + timedelta(days=6)

    if (date.today() - last_year_start).days < 365:
        return _empty(COMPARISON_SAME_WEEK_LAST_YEAR, STATUS_INSUFFICIENT_HISTORY)

    cur_num = _to_number(current_value.raw)
    if cur_num is None:
        return _empty(COMPARISON_SAME_WEEK_LAST_YEAR, STATUS_INSUFFICIENT_HISTORY)

    result = await query(
        hass,
        HistoryQuery(
            entity_id=provider.config["entity_id"],
            start_date=last_year_start,
            end_date=last_year_end,
            aggregation=HISTORY_AGG_MEAN,
        ),
    )
    valid = [v for v in result.data.values() if v is not None]
    if not valid:
        return _empty(COMPARISON_SAME_WEEK_LAST_YEAR, STATUS_INSUFFICIENT_HISTORY)

    reducer = _WEEKLY_AGG_REDUCERS.get(weekly_aggregation, _WEEKLY_AGG_REDUCERS["mean"])
    agg = reducer(valid)
    delta = cur_num - agg
    return Comparison(
        type=COMPARISON_SAME_WEEK_LAST_YEAR,
        value=agg,
        delta=delta,
        direction=_direction(delta),
        status=result.status,
        days_used=result.days_used,
    )


async def evaluate_comparisons(
    hass: HomeAssistant,
    provider: FieldProvider,
    current_value: FieldValue,
    logical_date: date,
    field_config: dict[str, Any],
    direction_preference: str,
) -> list[Comparison]:
    """Run every configured comparison for a field. Tag interpretation last."""
    results: list[Comparison] = []
    for spec in field_config.get("comparisons", []):
        ctype = spec.get("type")
        try:
            r = await _dispatch_one(hass, provider, current_value, logical_date, spec, ctype)
        except Exception:  # noqa: BLE001 — entry-point boundary; never crash brief
            _LOGGER.exception(
                "Comparison %s for %s failed", ctype, provider.config.get("entity_id")
            )
            r = _empty(str(ctype or "unknown"), STATUS_NOT_APPLICABLE)
        r.interpretation = compute_interpretation(r.direction, direction_preference)
        results.append(r)
    return results


async def _dispatch_one(
    hass: HomeAssistant,
    provider: FieldProvider,
    current_value: FieldValue,
    logical_date: date,
    spec: dict[str, Any],
    ctype: str | None,
) -> Comparison:
    """Route a single config entry to the right compare_* function."""
    if ctype == COMPARISON_YESTERDAY:
        return await compare_yesterday(provider, current_value, logical_date)
    if ctype == COMPARISON_SAME_WEEKDAY_LAST_WEEK:
        return await compare_same_weekday_last_week(provider, current_value, logical_date)
    if ctype == COMPARISON_ROLLING_AVG:
        return await compare_rolling_avg(
            hass, provider, current_value, logical_date, int(spec.get("window_days", 14))
        )
    if ctype == COMPARISON_ROLLING_MIN:
        return await compare_rolling_min(
            hass, provider, current_value, logical_date, int(spec.get("window_days", 14))
        )
    if ctype == COMPARISON_ROLLING_MAX:
        return await compare_rolling_max(
            hass, provider, current_value, logical_date, int(spec.get("window_days", 14))
        )
    if ctype == COMPARISON_TARGET_VALUE:
        return compare_target_value(current_value, float(spec["target"]))
    if ctype == COMPARISON_TREND:
        return await compare_trend(
            hass, provider, current_value, logical_date, int(spec.get("window_days", 14))
        )
    if ctype == COMPARISON_SAME_WEEK_LAST_YEAR:
        return await compare_same_week_last_year(
            hass,
            provider,
            current_value,
            logical_date,
            str(spec.get("weekly_aggregation", "mean")),
        )
    return _empty(str(ctype or "unknown"), STATUS_NOT_APPLICABLE)
