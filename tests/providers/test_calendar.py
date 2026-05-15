"""Tests for providers/calendar.py (Section 8.6)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant, ServiceRegistry

from custom_components.morning_brief.providers.calendar import CalendarProvider

ENTITY = "calendar.personal"


def _events_response(events: list[dict[str, str]]) -> dict[str, dict[str, list]]:
    return {ENTITY: {"events": events}}


async def test_returns_first_event_summary(hass: HomeAssistant) -> None:
    events = [
        {
            "summary": "Vet appointment",
            "start": "2026-05-16T10:00:00",
            "end": "2026-05-16T11:00:00",
        },
        {"summary": "Dinner", "start": "2026-05-17T19:00:00", "end": "2026-05-17T21:00:00"},
    ]
    with patch.object(
        ServiceRegistry,
        "async_call",
        AsyncMock(return_value=_events_response(events)),
    ):
        result = await CalendarProvider(
            hass, {"calendar_entity_id": ENTITY}
        ).get_current_value(date(2026, 5, 15))
    assert result.raw == "Vet appointment"
    assert len(result.extra["events"]) == 1


async def test_max_events_limits_returned_count(hass: HomeAssistant) -> None:
    events = [
        {"summary": f"Event {i}", "start": "2026-05-16T10:00:00", "end": "2026-05-16T11:00:00"}
        for i in range(5)
    ]
    with patch.object(
        ServiceRegistry,
        "async_call",
        AsyncMock(return_value=_events_response(events)),
    ):
        result = await CalendarProvider(
            hass, {"calendar_entity_id": ENTITY, "max_events": 3}
        ).get_current_value(date(2026, 5, 15))
    assert len(result.extra["events"]) == 3


async def test_summary_regex_filters(hass: HomeAssistant) -> None:
    events = [
        {
            "summary": "Vet appointment",
            "start": "2026-05-16T10:00:00",
            "end": "2026-05-16T11:00:00",
        },
        {"summary": "Dinner", "start": "2026-05-17T19:00:00", "end": "2026-05-17T21:00:00"},
        {"summary": "Vet checkup", "start": "2026-05-18T09:00:00", "end": "2026-05-18T10:00:00"},
    ]
    with patch.object(
        ServiceRegistry,
        "async_call",
        AsyncMock(return_value=_events_response(events)),
    ):
        result = await CalendarProvider(
            hass,
            {"calendar_entity_id": ENTITY, "summary_regex": "Vet", "max_events": 5},
        ).get_current_value(date(2026, 5, 15))
    summaries = [e["summary"] for e in result.extra["events"]]
    assert "Dinner" not in summaries
    assert len(summaries) == 2


async def test_no_events_returns_stale(hass: HomeAssistant) -> None:
    with patch.object(
        ServiceRegistry,
        "async_call",
        AsyncMock(return_value=_events_response([])),
    ):
        result = await CalendarProvider(
            hass, {"calendar_entity_id": ENTITY}
        ).get_current_value(date(2026, 5, 15))
    assert result.raw is None
    assert result.stale is True


async def test_service_failure_returns_stale_no_crash(hass: HomeAssistant) -> None:
    with patch.object(
        ServiceRegistry,
        "async_call",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await CalendarProvider(
            hass, {"calendar_entity_id": ENTITY}
        ).get_current_value(date(2026, 5, 15))
    assert result.raw is None
    assert result.stale is True


async def test_get_value_for_date_is_always_stale(hass: HomeAssistant) -> None:
    """Calendar is informational; past dates aren't queried."""
    result = await CalendarProvider(
        hass, {"calendar_entity_id": ENTITY}
    ).get_value_for_date(date(2026, 5, 1))
    assert result.raw is None
    assert result.stale is True


def test_detect_from_entity(hass: HomeAssistant) -> None:
    assert CalendarProvider.detect_from_entity(hass, "calendar.personal") == 0.95
    assert CalendarProvider.detect_from_entity(hass, "sensor.foo") == 0.0


def test_validate_config_rejects_non_calendar_entity(hass: HomeAssistant) -> None:
    errors = CalendarProvider(
        hass, {"calendar_entity_id": "sensor.foo"}
    ).validate_config()
    assert any("calendar." in e for e in errors)


def test_validate_config_rejects_invalid_regex(hass: HomeAssistant) -> None:
    errors = CalendarProvider(
        hass, {"calendar_entity_id": ENTITY, "summary_regex": "[invalid"}
    ).validate_config()
    assert any("regex" in e for e in errors)
