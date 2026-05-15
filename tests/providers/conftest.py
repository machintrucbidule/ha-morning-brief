"""Shared fixtures for provider tests."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.morning_brief.history import HistoryResult


@pytest.fixture
def history_ok() -> type[HistoryResult]:
    """Re-export HistoryResult so tests can build canned results easily."""
    return HistoryResult


def make_history_result(
    data: dict[date, float | None],
    status: str = "ok",
    sources: list[str] | None = None,
) -> HistoryResult:
    """Build a HistoryResult with sensible defaults for use in patches."""
    days_used = sum(1 for v in data.values() if v is not None)
    return HistoryResult(
        data=data,
        status=status,
        days_used=days_used,
        days_expected=len(data),
        sources_used=sources if sources is not None else (["lts"] if days_used else []),
    )
