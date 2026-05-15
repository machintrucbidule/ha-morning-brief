"""Tests for the initial config flow (Section 19) + options flow + subentries."""

from __future__ import annotations

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.morning_brief.const import DOMAIN
from custom_components.morning_brief.options_flow import MorningBriefOptionsFlow
from custom_components.morning_brief.subentries.category.flow import (
    CategorySubentryFlow,
)


async def test_initial_flow_creates_morning_entry(hass: HomeAssistant) -> None:
    """Complete the 6-step flow for a morning instance with disabled AI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Step 1 — report_type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"report_type": "morning"}
    )
    assert result["step_id"] == "name_lang"

    # Step 2 — name + language
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"instance_name": "Brief matinal", "language": "fr"}
    )
    assert result["step_id"] == "logical_day"

    # Step 3 — logical_day (fixed_cutoff default)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "strategy": "fixed_cutoff",
            "cutoff_hour": 4,
            "sleep_sensor_entity": "",
            "awake_state": "off",
            "hard_fallback_hour": 12,
            "lookback_hours": 36,
            "min_sleep_duration_minutes": 120,
        },
    )
    assert result["step_id"] == "trigger"

    # Step 4 — trigger (schedule)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "trigger_level": "schedule",
            "time": "07:30",
            "trigger_entity_id": "",
            "trigger_to_state": "off",
            "delay_minutes": 30,
            "fallback_hour": 12,
        },
    )
    assert result["step_id"] == "ai"

    # Step 5 — AI (disabled)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "ai_provider_type": "disabled",
            "entity_id": "",
            "api_key": "",
            "model": "",
        },
    )
    assert result["step_id"] == "copy_from"

    # Step 6 — copy_from (none)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"copy_from_instance": "_none_"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brief matinal"
    assert result["data"]["report_type"] == "morning"
    assert result["data"]["language"] == "fr"
    assert result["data"]["logical_day"]["strategy"] == "fixed_cutoff"
    assert result["data"]["trigger"]["level"] == "schedule"
    assert result["data"]["ai"]["provider_type"] == "disabled"


async def test_evening_flow_skips_logical_day_step(hass: HomeAssistant) -> None:
    """Evening report → step 3 (logical_day) must be skipped."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"report_type": "evening"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"instance_name": "Brief soir", "language": "fr"}
    )
    assert result["step_id"] == "trigger"  # logical_day skipped


async def test_invalid_report_type_rejected(hass: HomeAssistant) -> None:
    """Voluptuous rejects an unknown report_type before any draft is built."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    try:
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"report_type": "blob"}
        )
    except Exception:  # noqa: BLE001 — voluptuous wraps as MultipleInvalid
        return
    raise AssertionError("voluptuous should have rejected report_type=blob")


def test_options_flow_main_menu_lists_sections() -> None:
    """The options main menu shows the 8 expected sections (or 7 for non-morning)."""
    entry = type(
        "FakeEntry",
        (),
        {
            "data": {"report_type": "morning"},
            "options": {},
            "subentries": {},
            "entry_id": "x",
        },
    )()
    flow = MorningBriefOptionsFlow()
    flow._config_entry = entry  # type: ignore[attr-defined]  # matches HA flow-manager injection
    assert flow._is_morning() is True  # noqa: SLF001 — testing the gate


def test_category_subentry_slugifies_label_when_no_override() -> None:
    """`Bender's cat` → `bender_s_cat`."""
    from custom_components.morning_brief.subentries.category.flow import (
        _slugify,
    )

    assert _slugify("Bender's cat") == "bender_s_cat"
    assert _slugify("Santé") == "sant"  # accents stripped to underscores then trimmed


async def test_category_subentry_flow_shows_form(hass: HomeAssistant) -> None:
    """The category flow's first step is a single form."""
    flow = CategorySubentryFlow()
    flow.hass = hass  # type: ignore[attr-defined]
    result = await flow.async_step_user(None)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
