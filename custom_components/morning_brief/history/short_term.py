"""Short-term history wrapper.

Reads raw state changes from the recorder and exposes:
- `get_short_term`: list of state changes in a window
- `get_short_term_daily_aggregate`: those changes aggregated per day

Used as a fallback when LTS is absent for the requested window
(see hybrid.py and Section 10.3 of the spec). Uses `last_changed`,
NEVER `last_updated`, per G1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.recorder import history as recorder_history
from homeassistant.components.recorder.util import get_instance
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    HISTORY_AGG_LAST,
    HISTORY_AGG_MAX,
    HISTORY_AGG_MEAN,
    HISTORY_AGG_MIN,
    HISTORY_AGG_SUM,
)
from ..exceptions import HistoryError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class StateChange:
    """One state change as returned by the short-term history wrapper.

    `timestamp` is `last_changed` from the underlying State object — i.e.
    when the state value actually changed, NOT `last_updated` which fires
    on every heartbeat (G1).
    """

    timestamp: datetime
    state: str
    attributes: dict[str, Any]


def _to_state_change(state_obj: Any) -> StateChange:
    """Convert an HA `State` (or compatible) to our `StateChange`."""
    attrs = getattr(state_obj, "attributes", None) or {}
    return StateChange(
        timestamp=state_obj.last_changed,
        state=state_obj.state,
        attributes=dict(attrs),
    )


async def get_short_term(
    hass: HomeAssistant,
    entity_id: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> list[StateChange]:
    """Return state changes for `entity_id` over `[start_datetime, end_datetime]`.

    Ordered by timestamp ascending. Includes all states the recorder kept,
    including potentially `unavailable` / `unknown` — filtering is the
    caller's responsibility (event_detector handles that for the event-
    based and duration providers).

    Raises:
        HistoryError: if the recorder call fails.
    """
    try:
        recorder = get_instance(hass)
        rows_by_id = await recorder.async_add_executor_job(
            recorder_history.state_changes_during_period,
            hass,
            start_datetime,
            end_datetime,
            entity_id,
        )
    except Exception as err:  # noqa: BLE001 — wrap any recorder error
        raise HistoryError(f"Recorder short-term query failed: {err}") from err

    states = rows_by_id.get(entity_id, []) if rows_by_id else []
    changes = [_to_state_change(s) for s in states]
    changes.sort(key=lambda c: c.timestamp)
    return changes


def _coerce_float(state: str) -> float | None:
    """Parse a state string as a float, returning None for non-numeric inputs."""
    if state in (None, "", "unavailable", "unknown"):
        return None
    try:
        return float(state)
    except (TypeError, ValueError):
        return None


def _aggregate(values: list[float], aggregation: str) -> float | None:
    """Apply `aggregation` to a non-empty list of floats. Returns None if empty."""
    if not values:
        return None
    if aggregation == HISTORY_AGG_MEAN:
        return sum(values) / len(values)
    if aggregation == HISTORY_AGG_SUM:
        return sum(values)
    if aggregation == HISTORY_AGG_MAX:
        return max(values)
    if aggregation == HISTORY_AGG_MIN:
        return min(values)
    if aggregation == HISTORY_AGG_LAST:
        return values[-1]
    raise HistoryError(f"Unsupported short-term aggregation: {aggregation}")


async def get_short_term_daily_aggregate(
    hass: HomeAssistant,
    entity_id: str,
    start_date: date,
    end_date: date,
    aggregation: str,
) -> dict[date, float | None]:
    """Aggregate short-term values per local day over `[start_date, end_date]`.

    Returned dict is indexed by every date in the window; days with no
    valid numeric data are `None`.

    Args:
        hass: HA instance.
        entity_id: sensor to query.
        start_date / end_date: inclusive local-date window.
        aggregation: one of mean | sum | max | min | last.

    Raises:
        HistoryError: on recorder failure or unsupported aggregation.
    """
    if end_date < start_date:
        raise HistoryError("end_date is before start_date")

    start_dt = dt_util.start_of_local_day(start_date)
    end_dt = dt_util.start_of_local_day(end_date) + timedelta(days=1)

    changes = await get_short_term(hass, entity_id, start_dt, end_dt)

    # Initialise window with None for every expected day.
    out: dict[date, float | None] = {}
    cur = start_date
    while cur <= end_date:
        out[cur] = None
        cur += timedelta(days=1)

    # Bucket by local date.
    by_day: dict[date, list[float]] = {d: [] for d in out}
    for change in changes:
        value = _coerce_float(change.state)
        if value is None:
            continue
        local_day = dt_util.as_local(change.timestamp).date()
        if local_day in by_day:
            by_day[local_day].append(value)

    for day, values in by_day.items():
        out[day] = _aggregate(values, aggregation)

    return out
