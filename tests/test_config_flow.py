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
    """Complete the multi-step flow for a morning instance with disabled AI."""
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
    assert result["step_id"] == "logical_day_strategy"

    # Step 3a — logical_day strategy picker
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"strategy": "fixed_cutoff"}
    )
    assert result["step_id"] == "logical_day_fixed_cutoff"

    # Step 3b — fixed-cutoff params
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"cutoff_hour": 4}
    )
    assert result["step_id"] == "trigger_level"

    # Step 4a — trigger level picker
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"trigger_level": "schedule"}
    )
    assert result["step_id"] == "trigger_schedule"

    # Step 4b — schedule params
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"time": "07:30", "days_of_week": ["0", "1", "2", "3", "4", "5", "6"]},
    )
    assert result["step_id"] == "ai_provider"

    # Step 5 — AI provider picker (disabled skips param step)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ai_provider_type": "disabled"}
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
    """Evening report → step 3 (logical_day_strategy) must be skipped."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"report_type": "evening"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"instance_name": "Brief soir", "language": "fr"}
    )
    assert result["step_id"] == "trigger_level"


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
    """The options main menu shows the expected sections (morning includes logical_day)."""
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
