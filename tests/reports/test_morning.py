"""End-to-end tests for reports/morning.py (Section 14.2)."""

from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.ai.base import AIProvider
from custom_components.morning_brief.history import HistoryResult
from custom_components.morning_brief.reports.morning import MorningReport
from custom_components.morning_brief.types import AIResult, FieldValue

from .conftest import fake_category, fake_field, fresh_value


@contextmanager
def patched_resolve_pipeline(
    value: FieldValue, *, create_provider_side_effect: Any = None
):  # type: ignore[no-untyped-def]
    """Patch every layer the shared `_resolve_field` helper calls."""
    empty = HistoryResult(
        data={}, status="ok", days_used=0, days_expected=0, sources_used=[]
    )
    if create_provider_side_effect is None:
        provider_mock = MagicMock(
            config={"entity_id": "sensor.weight"},
            get_current_value=AsyncMock(return_value=value),
            get_value_for_date=AsyncMock(return_value=value),
        )
        create_kwargs: dict[str, Any] = {"return_value": provider_mock}
    else:
        create_kwargs = {"side_effect": create_provider_side_effect}

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "custom_components.morning_brief.reports.base.create_provider",
                **create_kwargs,
            )
        )
        stack.enter_context(
            patch(
                "custom_components.morning_brief.reports.base.apply_gate",
                AsyncMock(side_effect=lambda _h, fv, *_a, **_k: fv),
            )
        )
        stack.enter_context(
            patch(
                "custom_components.morning_brief.reports.base.evaluate_comparisons",
                AsyncMock(return_value=[]),
            )
        )
        stack.enter_context(
            patch(
                "custom_components.morning_brief.reports.base.query",
                AsyncMock(return_value=empty),
            )
        )
        yield


async def test_build_happy_path(hass: HomeAssistant, fake_coordinator: SimpleNamespace) -> None:
    """One field + one category + AI-disabled envelope → canonical dict."""
    with patched_resolve_pipeline(fresh_value(75.5)):
        brief = await MorningReport(hass, fake_coordinator).build(date(2026, 5, 15))
    assert brief["schema_version"] == 1
    assert brief["meta"]["report_type"] == "morning"
    assert brief["meta"]["logical_date"] == "2026-05-15"
    # AI returned a valid envelope from the disabled provider → ai_status disabled.
    assert brief["meta"]["ai_status"] == "disabled"
    assert brief["meta"]["ai_provider"] == "disabled"


async def test_build_skips_fields_not_visible_in_morning(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    """A field with visible_in=[weekly] is ignored by the morning builder."""
    fake_coordinator.fields = [fake_field(visible_in=["weekly"])]
    with patched_resolve_pipeline(fresh_value()):
        brief = await MorningReport(hass, fake_coordinator).build(date(2026, 5, 15))
    # Category drops its only (filtered) field → empty category list.
    assert brief["categories"] == []


async def test_build_degraded_when_ai_returns_invalid_json(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    """An AI response that doesn't parse → ai_status=degraded, empty insights."""
    ai = MagicMock(spec=AIProvider)
    ai.provider_type = "anthropic_direct"
    ai.generate = AsyncMock(
        return_value=AIResult(status="ok", content="not json", tokens_used=0)
    )
    fake_coordinator.ai_provider = ai
    with (
        patched_resolve_pipeline(fresh_value()),
        patch("custom_components.morning_brief.ai.retry.asyncio.sleep", AsyncMock()),
    ):
        brief = await MorningReport(hass, fake_coordinator).build(date(2026, 5, 15))
    assert brief["meta"]["ai_status"] == "degraded"
    assert brief["ai_output"]["verdict"] == ""


async def test_build_propagates_ai_envelope_into_ai_output(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    """A successful AI call merges insights + verdict into ai_output."""
    envelope = {
        "alertes_formulees": [],
        "insights": {"health": "Good rest"},
        "weather_synthesis": "Sunny day ahead.",
        "verdict": "Have a great morning.",
    }
    ai = MagicMock(spec=AIProvider)
    ai.provider_type = "ha_ai_task"
    ai.generate = AsyncMock(
        return_value=AIResult(status="ok", content=json.dumps(envelope))
    )
    fake_coordinator.ai_provider = ai
    with patched_resolve_pipeline(fresh_value()):
        brief = await MorningReport(hass, fake_coordinator).build(date(2026, 5, 15))
    assert brief["meta"]["ai_status"] == "ok"
    assert brief["ai_output"]["verdict"] == "Have a great morning."
    assert brief["ai_output"]["weather_synthesis"] == "Sunny day ahead."
    assert brief["ai_output"]["category_insights"] == {"health": "Good rest"}


async def test_build_bad_field_does_not_crash_brief(
    hass: HomeAssistant, fake_coordinator: SimpleNamespace
) -> None:
    """If `_resolve_field` raises, the brief is still produced (R6)."""
    fake_coordinator.fields = [
        fake_field(field_id="bad", provider_config={"entity_id": ""}),
        fake_field(field_id="good"),
    ]
    fake_coordinator.categories = [fake_category()]
    call_count = {"n": 0}

    def fake_create_provider(_h: object, _t: object, _c: object) -> MagicMock:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("bad provider config")
        return MagicMock(
            config={"entity_id": "sensor.weight"},
            get_current_value=AsyncMock(return_value=fresh_value()),
            get_value_for_date=AsyncMock(return_value=fresh_value()),
        )

    with patched_resolve_pipeline(
        fresh_value(), create_provider_side_effect=fake_create_provider
    ):
        brief = await MorningReport(hass, fake_coordinator).build(date(2026, 5, 15))
    field_ids = [f["id"] for c in brief["categories"] for f in c["fields"]]
    assert field_ids == ["good"]
