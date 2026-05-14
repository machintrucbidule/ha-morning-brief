"""Hybrid history abstraction over the HA recorder.

Callers import from this package; the LTS / short-term split is an
implementation detail (D10, G7). See `MORNING_BRIEF_SPEC.md` Section 10.
"""

from .event_detector import filter_valid_changes
from .hybrid import (
    HistoryQuery,
    HistoryResult,
    get_recorder_retention,
    query,
)
from .lts import entity_has_lts, get_lts_daily
from .short_term import (
    StateChange,
    get_short_term,
    get_short_term_daily_aggregate,
)

__all__ = [
    "HistoryQuery",
    "HistoryResult",
    "StateChange",
    "entity_has_lts",
    "filter_valid_changes",
    "get_lts_daily",
    "get_recorder_retention",
    "get_short_term",
    "get_short_term_daily_aggregate",
    "query",
]
