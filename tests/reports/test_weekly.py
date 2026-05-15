"""End-to-end tests for reports/weekly.py (Section 14.4, D13, G15)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.history import HistoryResult
from custom_components.morning_brief.reports.weekly import WeeklyReport, _week_window

from .conftest import fake_field


def _seven_days_back(end: date) -> list[date]:
    from datetime import timedelta

    return [end - timedelta(days=6 - i) for i in range(7)]


def test_week_window_default_iso_monday_start() -> None:
    """logical_date=2026-05-15 (Fri) with start_day=0 (Mon) → 11→17."""
    start, end = _week_window(date(2026, 5, 15), 0)
    assert start == date(2026, 5, 11)
    assert end == date(2026, 5, 17)


def test_week_window_sunday_start() -> None:
    """start_day=6 (Sun): 2026-05-15 (Fri) anchors to 2026-05-10 → 16."""
    start, end = _week_window(date(2026, 5, 15), 6)
    assert start == date(2026, 5, 10)
    assert end == date(2026, 5, 16)


async def test_build_aggregates_daily_values_per_field(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    fake_coordinator.fields = [
        fake_field(
            visible_in=["weekly"],
            weekly_aggregation="mean",
            provider_type="instantaneous",
        )
    ]
    days = _seven_days_back(date(2026, 5, 17))
    values = [60.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0]
    history = HistoryResult(
        data=dict(zip(days, values, strict=False)),
        status="ok",
        days_used=7,
        days_expected=7,
        sources_used=["lts"],
    )

    with (
        patch(
            "custom_components.morning_brief.reports.weekly.create_provider",
            return_value=MagicMock(config={"entity_id": "sensor.x"}),
        ),
        patch(
            "custom_components.morning_brief.reports.weekly.query",
            AsyncMock(return_value=history),
        ),
        patch(
            "custom_components.morning_brief.reports.weekly.evaluate_comparisons",
            AsyncMock(return_value=[]),
        ),
    ):
        brief = await WeeklyReport(hass, fake_coordinator).build(date(2026, 5, 17))

    fields = brief["categories"][0]["fields"]
    assert len(fields) == 1
    assert fields[0]["value"]["raw"] == 63.0  # mean of 60..66
    assert fields[0]["sparkline_data"] == values


async def test_build_marks_stale_when_no_data(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    fake_coordinator.fields = [
        fake_field(visible_in=["weekly"], weekly_aggregation="mean")
    ]
    empty = HistoryResult(
        data={}, status="insufficient_history", days_used=0, days_expected=7,
        sources_used=[],
    )
    with (
        patch(
            "custom_components.morning_brief.reports.weekly.create_provider",
            return_value=MagicMock(config={"entity_id": "sensor.x"}),
        ),
        patch(
            "custom_components.morning_brief.reports.weekly.query",
            AsyncMock(return_value=empty),
        ),
        patch(
            "custom_components.morning_brief.reports.weekly.evaluate_comparisons",
            AsyncMock(return_value=[]),
        ),
    ):
        brief = await WeeklyReport(hass, fake_coordinator).build(date(2026, 5, 17))

    field = brief["categories"][0]["fields"][0]
    assert field["value"]["raw"] is None
    assert field["value"]["stale"] is True


async def test_build_filters_visible_in_weekly(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    fake_coordinator.fields = [fake_field(visible_in=["morning"])]
    with (
        patch(
            "custom_components.morning_brief.reports.weekly.create_provider",
            return_value=MagicMock(config={"entity_id": "sensor.x"}),
        ),
        patch(
            "custom_components.morning_brief.reports.weekly.query",
            AsyncMock(
                return_value=HistoryResult(
                    data={}, status="ok", days_used=0, days_expected=0, sources_used=[]
                )
            ),
        ),
    ):
        brief = await WeeklyReport(hass, fake_coordinator).build(date(2026, 5, 17))
    assert brief["categories"] == []


async def test_build_uses_change_aggregation_for_cumulative(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    """Cumulative sensors must query LTS with the `change` statistic, not `mean`."""
    fake_coordinator.fields = [
        fake_field(
            field_id="steps",
            provider_type="cumulative",
            provider_config={"entity_id": "sensor.steps", "reset_hour": 0},
            visible_in=["weekly"],
            weekly_aggregation="sum",
            unit="",
        )
    ]
    captured: dict[str, str] = {}

    async def fake_query(_hass: object, q: object) -> HistoryResult:
        captured["aggregation"] = q.aggregation  # type: ignore[attr-defined]
        return HistoryResult(
            data={date(2026, 5, 11) + __import__("datetime").timedelta(days=i): 1000.0
                  for i in range(7)},
            status="ok",
            days_used=7,
            days_expected=7,
            sources_used=["lts"],
        )

    with (
        patch(
            "custom_components.morning_brief.reports.weekly.create_provider",
            return_value=MagicMock(config={"entity_id": "sensor.steps"}),
        ),
        patch(
            "custom_components.morning_brief.reports.weekly.query",
            side_effect=fake_query,
        ),
        patch(
            "custom_components.morning_brief.reports.weekly.evaluate_comparisons",
            AsyncMock(return_value=[]),
        ),
    ):
        brief = await WeeklyReport(hass, fake_coordinator).build(date(2026, 5, 17))

    assert captured["aggregation"] == "change"
    assert brief["categories"][0]["fields"][0]["value"]["raw"] == 7000.0
