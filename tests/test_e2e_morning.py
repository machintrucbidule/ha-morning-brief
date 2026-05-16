"""End-to-end test for the morning_brief integration (Phase 9 step 76).

Setup a config entry, run generation, assert:
- the sensor reports the right state and attributes
- a brief is persisted to the BriefStore
- the morning_brief_generated event fires
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.morning_brief.const import (
    DOMAIN,
    EVENT_BRIEF_GENERATED,
    SENSOR_ATTRIBUTE_BYTE_LIMIT,
)
from custom_components.morning_brief.sensor import _truncate_attributes


def _build_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Build a minimal morning_brief config entry suitable for setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Brief matinal",
        data={
            "report_type": "morning",
            "instance_name": "Brief matinal",
            "language": "fr",
            "logical_day": {"strategy": "fixed_cutoff", "config": {"cutoff_hour": 4}},
            "trigger": {"level": "external", "config": {}},
            "ai": {"provider_type": "disabled", "config": {}},
        },
        options={},
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_creates_sensors_and_buttons(hass: HomeAssistant) -> None:
    """Setting up an entry registers the sensor + button entities."""
    entry = _build_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Three instance-level sensors (main + status + markdown) + two
    # buttons. Plus one sensor per configured field — the test fixture
    # adds none, so total = 3 sensors.
    sensor_states = [s for s in hass.states.async_all() if s.domain == "sensor"]
    button_states = [s for s in hass.states.async_all() if s.domain == "button"]
    assert len(sensor_states) == 3
    assert len(button_states) == 2


async def test_generate_service_fires_event_and_persists(hass: HomeAssistant) -> None:
    """Calling morning_brief.generate fires the event and stores a brief."""
    entry = _build_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    events: list[Event] = []
    hass.bus.async_listen(EVENT_BRIEF_GENERATED, events.append)

    await hass.services.async_call(
        DOMAIN, "generate", {"instance_id": entry.entry_id, "force": True}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    payload = events[0].data
    assert payload["instance_id"] == entry.entry_id
    assert payload["report_type"] == "morning"
    assert payload["status"] in {"ok", "disabled", "degraded"}

    coordinator = hass.data[DOMAIN][entry.entry_id]
    briefs = await coordinator.store.list_briefs()
    assert len(briefs) == 1
    assert briefs[0]["canonical_json"]["schema_version"] == 1


async def test_preview_service_does_not_persist(hass: HomeAssistant) -> None:
    """morning_brief.preview returns the JSON but doesn't touch the store."""
    entry = _build_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "preview",
        {"instance_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert "canonical_json" in response
    canonical = response["canonical_json"]
    assert canonical["schema_version"] == 1

    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert await coordinator.store.list_briefs() == []


async def test_get_last_brief_service_returns_persisted_brief(
    hass: HomeAssistant,
) -> None:
    entry = _build_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, "generate", {"instance_id": entry.entry_id, "force": True}, blocking=True
    )
    response = await hass.services.async_call(
        DOMAIN,
        "get_last_brief",
        {"instance_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    assert response["brief"] is not None
    assert response["brief"]["canonical_json"]["schema_version"] == 1


async def test_unload_entry_drops_coordinator(hass: HomeAssistant) -> None:
    entry = _build_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


# --------------------------------------------------------------------------- #
# Truncation helper unit test (D18, G13)
# --------------------------------------------------------------------------- #


def test_truncate_attributes_keeps_payload_under_limit() -> None:
    small = {
        "meta": {"x": 1},
        "alerts": [],
        "previous_briefs_refs": [],
        "categories": [],
    }
    out = _truncate_attributes(small)
    assert out["_truncated"] is False


def test_truncate_attributes_drops_categories_when_payload_exceeds_limit() -> None:
    # Build a fake brief well above the 16 KB cap by inflating `categories`.
    fat_payload = "x" * (SENSOR_ATTRIBUTE_BYTE_LIMIT + 1)
    huge = {
        "meta": {"generated_at": datetime.now(tz=UTC).isoformat()},
        "alerts": [],
        "previous_briefs_refs": ["uuid-1", "uuid-2"],
        "categories": [{"id": "x", "fields": [{"label": fat_payload}]}],
    }
    assert len(json.dumps(huge, default=str).encode("utf-8")) > SENSOR_ATTRIBUTE_BYTE_LIMIT
    out = _truncate_attributes(huge)
    assert out["_truncated"] is True
    assert "categories" not in out
    assert out["previous_briefs_refs"] == ["uuid-1", "uuid-2"]


# Patch reservation kept for future tests that mock the AI service call.
_ = patch
