"""Filter raw state changes into clean "event" sequences.

Pure functions; no HA / no recorder / no I/O. Used by the `event_based`
and `duration` providers to honour the spec's event-detection rules
(D23, G1):

1. Reject `unavailable` / `unknown` state values.
2. Deduplicate consecutive identical numeric values (within `epsilon`).
3. Apply a debounce window: when two consecutive *valid* events are
   closer than `min_debounce_seconds` apart, keep only the FIRST.
"""

from __future__ import annotations

from ..const import DEFAULT_EVENT_EPSILON, DEFAULT_MIN_DEBOUNCE_SECONDS
from .short_term import StateChange

_INVALID_STATES: frozenset[str] = frozenset({"unavailable", "unknown", "", "None"})


def _to_number(state: str) -> float | None:
    """Parse a state string as a float; None if not numeric."""
    try:
        return float(state)
    except (TypeError, ValueError):
        return None


def filter_valid_changes(
    changes: list[StateChange],
    epsilon: float = DEFAULT_EVENT_EPSILON,
    min_debounce_seconds: int = DEFAULT_MIN_DEBOUNCE_SECONDS,
) -> list[StateChange]:
    """Return a filtered, debounced view of `changes`.

    The input is assumed to be ordered by `timestamp` ascending (this is
    how `short_term.get_short_term` returns it). If callers pass an
    unordered list we sort defensively.

    Args:
        changes: list of state changes to filter.
        epsilon: minimum |delta| to count as a real change. Two
            consecutive numeric values within `epsilon` of each other are
            collapsed (the first is kept). `0.0` means "drop only exact
            duplicates".
        min_debounce_seconds: minimum gap between two consecutive valid
            events. If a follow-up event arrives sooner, it is dropped
            (the first wins).

    Returns:
        A new list of `StateChange` instances, ordered by timestamp.
    """
    if not changes:
        return []

    ordered = sorted(changes, key=lambda c: c.timestamp)

    out: list[StateChange] = []
    last_numeric: float | None = None
    last_kept_ts = None

    for change in ordered:
        # Rule 1: reject sentinel states.
        if change.state in _INVALID_STATES:
            continue

        numeric = _to_number(change.state)

        # Rule 2: dedupe consecutive numeric values within epsilon.
        if (
            numeric is not None
            and last_numeric is not None
            and abs(numeric - last_numeric) <= epsilon
        ):
            continue

        # Rule 3: debounce — drop events arriving too soon after the last kept one.
        if last_kept_ts is not None:
            elapsed = (change.timestamp - last_kept_ts).total_seconds()
            if elapsed < min_debounce_seconds:
                continue

        out.append(change)
        last_kept_ts = change.timestamp
        if numeric is not None:
            last_numeric = numeric

    return out
