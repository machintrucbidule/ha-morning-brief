"""Hybrid history orchestrator.

The single public entry point used by Phase 5 comparisons. Hides the
LTS-vs-short-term distinction behind one `query()` call:

1. Try LTS first when the entity exposes `state_class` (D10).
2. Fill any remaining gaps with short-term data, bounded by the
   recorder's `purge_keep_days` (G7) — older days the recorder no longer
   holds cannot be filled.
3. Compute a gap-aware status per D11.

LTS wins on conflict because LTS is the canonical historical record;
short-term gets pruned and is only used to plug gaps the recorder hasn't
yet rolled up into LTS (D10).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    DEFAULT_RECORDER_RETENTION_DAYS,
    PARTIAL_GAP_THRESHOLD,
    STATUS_INSUFFICIENT_HISTORY,
    STATUS_OK,
    STATUS_PARTIAL,
    STATUS_UNRELIABLE,
)
from ..exceptions import HistoryError
from .lts import entity_has_lts, get_lts_daily
from .short_term import get_short_term_daily_aggregate

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistoryQuery:
    """One history query: a date window + aggregation for one entity."""

    entity_id: str
    start_date: date
    end_date: date
    aggregation: str  # mean | change | sum | max | min | last


@dataclass
class HistoryResult:
    """Result of running a `HistoryQuery` through the hybrid layer."""

    data: dict[date, float | None]
    status: str  # STATUS_OK | STATUS_PARTIAL | STATUS_INSUFFICIENT_HISTORY | STATUS_UNRELIABLE
    days_used: int
    days_expected: int
    sources_used: list[str] = field(default_factory=list)


def get_recorder_retention(hass: HomeAssistant) -> int:
    """Return the recorder's actual `purge_keep_days`, or HA's default fallback.

    The recorder's retention is configurable per user (G7) — do NOT hardcode
    10 days. We read it off the recorder instance; if that lookup fails (or
    the attribute name changes across HA versions) we fall back to
    `DEFAULT_RECORDER_RETENTION_DAYS`.
    """
    try:
        recorder = get_instance(hass)
    except Exception:  # noqa: BLE001 — defensive at the boundary
        return DEFAULT_RECORDER_RETENTION_DAYS

    for attr in ("keep_days", "purge_keep_days", "_keep_days"):
        value = getattr(recorder, attr, None)
        if isinstance(value, int) and value > 0:
            return value
    return DEFAULT_RECORDER_RETENTION_DAYS


def _iter_dates(start_date: date, end_date: date) -> list[date]:
    """Inclusive date range."""
    return [
        date.fromordinal(o)
        for o in range(start_date.toordinal(), end_date.toordinal() + 1)
    ]


def _compute_status(days_used: int, days_expected: int) -> str:
    """Map (days_used, days_expected) to a comparison status enum (D11)."""
    if days_used == 0:
        return STATUS_INSUFFICIENT_HISTORY
    missing = days_expected - days_used
    if missing == 0:
        return STATUS_OK
    if missing / days_expected >= PARTIAL_GAP_THRESHOLD:
        return STATUS_UNRELIABLE
    return STATUS_PARTIAL


def _merge_filling_gaps(
    base: dict[date, float | None],
    source: dict[date, float | None],
) -> int:
    """Copy values from `source` into `base` only where `base` is None.

    Returns the number of cells filled. LTS-wins-on-conflict (D10) falls
    out naturally from this rule: we never overwrite an existing value.
    """
    filled = 0
    for d, value in source.items():
        if value is None:
            continue
        if d in base and base[d] is None:
            base[d] = value
            filled += 1
    return filled


async def query(hass: HomeAssistant, q: HistoryQuery) -> HistoryResult:
    """Run a hybrid LTS-then-short-term query.

    Phase 2 contract:
    - Return a HistoryResult with `data` indexed by every date in the window.
    - `sources_used` reflects what was actually consulted (in order).
    - Never raises; all underlying failures are logged and degrade the
      status. Callers can rely on always getting a HistoryResult.
    """
    expected_dates = _iter_dates(q.start_date, q.end_date)
    expected_days = len(expected_dates)
    data: dict[date, float | None] = {d: None for d in expected_dates}
    sources: list[str] = []

    # 1. LTS first (D10).
    if entity_has_lts(hass, q.entity_id):
        try:
            lts_data = await get_lts_daily(
                hass, q.entity_id, q.start_date, q.end_date, q.aggregation
            )
        except HistoryError as err:
            _LOGGER.warning("LTS query failed for %s: %s", q.entity_id, err)
        else:
            if _merge_filling_gaps(data, lts_data) >= 0:
                sources.append("lts")

    # 2. Short-term fallback for gaps still present, bounded by recorder retention.
    if any(v is None for v in data.values()):
        retention = get_recorder_retention(hass)
        today = dt_util.now().date()
        earliest_short_term = today - timedelta(days=retention)
        st_start = max(q.start_date, earliest_short_term)
        if st_start <= q.end_date:
            try:
                st_data = await get_short_term_daily_aggregate(
                    hass, q.entity_id, st_start, q.end_date, q.aggregation
                )
            except HistoryError as err:
                _LOGGER.warning(
                    "Short-term query failed for %s: %s", q.entity_id, err
                )
            else:
                if _merge_filling_gaps(data, st_data) > 0:
                    sources.append("short_term")

    days_used = sum(1 for v in data.values() if v is not None)
    status = _compute_status(days_used, expected_days)

    return HistoryResult(
        data=data,
        status=status,
        days_used=days_used,
        days_expected=expected_days,
        sources_used=sources,
    )


__all__ = [
    "HistoryQuery",
    "HistoryResult",
    "get_recorder_retention",
    "query",
]
