"""Tests for history/event_detector.py (Section 10.4 + D23 + G1)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.util import dt as dt_util

from custom_components.morning_brief.history.event_detector import filter_valid_changes
from custom_components.morning_brief.history.short_term import StateChange


def _t(d: date, hour: int, minute: int = 0) -> datetime:
    """Local datetime helper."""
    return dt_util.start_of_local_day(d) + timedelta(hours=hour, minutes=minute)


def _change(state: str, ts: datetime) -> StateChange:
    return StateChange(timestamp=ts, state=state, attributes={})


D = date(2026, 5, 10)


def test_empty_input_returns_empty() -> None:
    assert filter_valid_changes([]) == []


def test_rejects_unavailable_and_unknown() -> None:
    """Sentinel states are dropped (G1)."""
    changes = [
        _change("1", _t(D, 0)),
        _change("unavailable", _t(D, 1)),
        _change("unknown", _t(D, 2)),
        _change("", _t(D, 3)),
        _change("2", _t(D, 4)),
    ]
    # min_debounce=0 so timing isn't a confound here.
    out = filter_valid_changes(changes, min_debounce_seconds=0)
    assert [c.state for c in out] == ["1", "2"]


def test_dedupes_consecutive_identical_numeric_values_with_epsilon_zero() -> None:
    """epsilon=0 collapses exact duplicates."""
    changes = [
        _change("10", _t(D, 0)),
        _change("10", _t(D, 1)),  # exact duplicate → drop
        _change("11", _t(D, 2)),
    ]
    out = filter_valid_changes(changes, epsilon=0.0, min_debounce_seconds=0)
    assert [c.state for c in out] == ["10", "11"]


def test_dedup_with_positive_epsilon() -> None:
    """epsilon=0.5: consecutive values within 0.5 are collapsed."""
    changes = [
        _change("70.0", _t(D, 0)),
        _change("70.3", _t(D, 1)),  # |delta|=0.3 → drop
        _change("70.7", _t(D, 2)),  # |70.7 - 70.0|=0.7 > 0.5 → keep
        _change("70.8", _t(D, 3)),  # |70.8 - 70.7|=0.1 → drop
    ]
    out = filter_valid_changes(changes, epsilon=0.5, min_debounce_seconds=0)
    assert [c.state for c in out] == ["70.0", "70.7"]


def test_debounce_drops_rapid_followups_and_keeps_first() -> None:
    """When two events fall inside `min_debounce_seconds`, the FIRST wins."""
    changes = [
        _change("100", _t(D, 0, 0)),
        _change("110", _t(D, 0, 2)),  # 2 min later, debounce=5 min → drop
        _change("120", _t(D, 0, 4)),  # 4 min after first → drop
        _change("130", _t(D, 0, 6)),  # 6 min after first kept → keep
    ]
    out = filter_valid_changes(changes, epsilon=0.0, min_debounce_seconds=300)
    assert [c.state for c in out] == ["100", "130"]


def test_debounce_window_applies_from_last_kept_not_last_seen() -> None:
    """The 'last_kept_ts' counter is what debounce uses (the dropped ones don't restart it)."""
    changes = [
        _change("1", _t(D, 0, 0)),
        _change("2", _t(D, 0, 4)),  # dropped (4 min < 5 min)
        _change("3", _t(D, 0, 6)),  # 6 min from "1" → keep
        _change("4", _t(D, 0, 9)),  # 3 min from "3" → drop
    ]
    out = filter_valid_changes(changes, epsilon=0.0, min_debounce_seconds=300)
    assert [c.state for c in out] == ["1", "3"]


def test_sorts_input_before_filtering() -> None:
    """Out-of-order input is sorted by timestamp before rules run."""
    changes = [
        _change("3", _t(D, 2)),
        _change("1", _t(D, 0)),
        _change("2", _t(D, 1)),
    ]
    out = filter_valid_changes(changes, epsilon=0.0, min_debounce_seconds=0)
    assert [c.state for c in out] == ["1", "2", "3"]


def test_non_numeric_states_bypass_epsilon_dedup() -> None:
    """Non-numeric strings can't be compared via epsilon — they pass the dedup rule.

    (Debounce still applies to them, but with min_debounce_seconds=0 nothing is dropped.)
    """
    changes = [
        _change("Bleu", _t(D, 0)),
        _change("Bleu", _t(D, 1)),
        _change("Rouge", _t(D, 2)),
    ]
    out = filter_valid_changes(changes, epsilon=0.0, min_debounce_seconds=0)
    assert [c.state for c in out] == ["Bleu", "Bleu", "Rouge"]
