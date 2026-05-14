"""Long-term statistics (LTS) wrapper.

Reads daily statistics from Home Assistant's recorder. The returned dict is
indexed by `date` so callers can iterate over expected days and look up
without worrying about missing buckets (G3 — recorder skips empty days).

See MORNING_BRIEF_SPEC.md Section 10.2.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.recorder import statistics
from homeassistant.components.recorder.util import get_instance
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    HISTORY_AGG_CHANGE,
    HISTORY_AGG_MAX,
    HISTORY_AGG_MEAN,
    HISTORY_AGG_MIN,
    HISTORY_AGG_SUM,
)
from ..exceptions import HistoryError

_LOGGER = logging.getLogger(__name__)

# Aggregations the LTS layer can serve. "last" is not in this set — there is
# no LTS bucket for "last value of the day"; callers must use short-term.
_LTS_AGGREGATIONS: frozenset[str] = frozenset(
    {
        HISTORY_AGG_MEAN,
        HISTORY_AGG_CHANGE,
        HISTORY_AGG_SUM,
        HISTORY_AGG_MAX,
        HISTORY_AGG_MIN,
    }
)


def entity_has_lts(hass: HomeAssistant, entity_id: str) -> bool:
    """Heuristic: an entity ships LTS iff it exposes `state_class` (G2).

    Note: this is a *necessary* condition, not sufficient — a sensor with
    `state_class` may still have partial or zero LTS rows (G2). Callers
    should treat a True result as "LTS may exist; try fetching".
    """
    state = hass.states.get(entity_id)
    if state is None:
        return False
    return state.attributes.get("state_class") is not None


def _iter_dates(start_date: date, end_date: date) -> list[date]:
    """Return every date in [start_date, end_date] inclusive."""
    return [
        date.fromordinal(o)
        for o in range(start_date.toordinal(), end_date.toordinal() + 1)
    ]


def _parse_bucket_start(start: Any) -> date | None:
    """Read the `start` field of an LTS row as a date.

    Newer HA versions return a `datetime`; older ones return a Unix timestamp
    float. Both are accepted. The bucket represents local-midnight-aligned
    days, so we convert back to local time before taking `.date()`.
    """
    if isinstance(start, datetime):
        dt = start if start.tzinfo is not None else start.replace(tzinfo=dt_util.UTC)
    elif isinstance(start, (int, float)):
        dt = datetime.fromtimestamp(float(start), tz=dt_util.UTC)
    else:
        return None
    return dt_util.as_local(dt).date()


async def get_lts_daily(
    hass: HomeAssistant,
    entity_id: str,
    start_date: date,
    end_date: date,
    aggregation: str,
) -> dict[date, float | None]:
    """Fetch daily LTS for `entity_id` over `[start_date, end_date]`.

    Args:
        hass: the Home Assistant instance.
        entity_id: the sensor to query.
        start_date: first day of the window (inclusive, local).
        end_date: last day of the window (inclusive, local).
        aggregation: one of mean | change | sum | max | min.

    Returns:
        A dict keyed by every date in the window; the value is the
        statistic for that day or `None` if the recorder has no bucket.

    Raises:
        HistoryError: if the aggregation is not supported by LTS, if the
            entity has no LTS at all, or if the recorder call fails.
    """
    if aggregation not in _LTS_AGGREGATIONS:
        raise HistoryError(f"Unsupported LTS aggregation: {aggregation}")
    if not entity_has_lts(hass, entity_id):
        raise HistoryError(f"Entity {entity_id} has no LTS (no state_class)")
    if end_date < start_date:
        raise HistoryError("end_date is before start_date")

    start_dt = dt_util.start_of_local_day(start_date)
    end_dt = dt_util.start_of_local_day(end_date) + timedelta(days=1)

    try:
        recorder = get_instance(hass)
        rows_by_id = await recorder.async_add_executor_job(
            statistics.statistics_during_period,
            hass,
            start_dt,
            end_dt,
            {entity_id},
            "day",
            None,
            {aggregation},
        )
    except Exception as err:  # noqa: BLE001 — wrap any recorder error
        raise HistoryError(f"Recorder LTS query failed: {err}") from err

    out: dict[date, float | None] = {d: None for d in _iter_dates(start_date, end_date)}

    rows: list[dict[str, Any]] = rows_by_id.get(entity_id, [])
    for row in rows:
        bucket_date = _parse_bucket_start(row.get("start"))
        if bucket_date is None or bucket_date not in out:
            continue
        value: Any = row.get(aggregation)
        if value is None:
            continue
        try:
            out[bucket_date] = float(value)
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Non-numeric LTS bucket for %s @ %s: %r — skipped",
                entity_id,
                bucket_date,
                value,
            )

    return out
