"""End-to-end tests for reports/evening.py (Section 14.3)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.reports.evening import EveningReport

from .conftest import fake_field, fresh_value
from .test_morning import patched_resolve_pipeline


async def test_evening_report_type_is_evening(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    fake_coordinator.fields = [fake_field(visible_in=["evening"])]
    with patched_resolve_pipeline(fresh_value()):
        brief = await EveningReport(hass, fake_coordinator).build(date(2026, 5, 15))
    assert brief["meta"]["report_type"] == "evening"


async def test_evening_filter_drops_morning_only_fields(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    fake_coordinator.fields = [fake_field(visible_in=["morning"])]
    with patched_resolve_pipeline(fresh_value()):
        brief = await EveningReport(hass, fake_coordinator).build(date(2026, 5, 15))
    assert brief["categories"] == []


async def test_evening_forces_cal_offset_zero(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    """Even if the caller passes cal_offset=1, evening report ignores it."""
    fake_coordinator.fields = [fake_field(visible_in=["evening"])]
    with patched_resolve_pipeline(fresh_value()):
        brief = await EveningReport(hass, fake_coordinator).build(
            date(2026, 5, 15), cal_offset=1
        )
    assert brief["meta"]["logical_day_offset"] == 0
