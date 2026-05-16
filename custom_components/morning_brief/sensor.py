# rationale: ~210 LOC because we now expose one sensor per configured
# field in addition to the two instance-level sensors. Splitting per
# class would scatter the shared DeviceInfo + state-extraction helpers.
"""Sensor entities for the morning_brief integration (Section 18.1).

Per instance:
- ``sensor.morning_brief_<slug>`` — main. State = ai_status.
  Attributes = the full canonical JSON (truncated past 16 KB per D18/G13).
- ``sensor.morning_brief_<slug>_status`` — lightweight (last gen, etc.).
- ``sensor.morning_brief_<slug>_markdown`` — full rendered markdown
  brief (for users who want to read the brief without installing the
  card, via Developer Tools → States).
- ``sensor.morning_brief_<slug>_<field_id>`` — one per configured field.
  State = the field's formatted value from the latest brief. Attributes
  carry the comparisons + anomaly info. Makes every captured value
  visible in HA UI / history / automations without the Lovelace card.
"""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SENSOR_ATTRIBUTE_BYTE_LIMIT,
    SENSOR_STATE_NO_DATA,
    SENSOR_STATE_OK,
)
from .coordinator import MorningBriefCoordinator
from .rendering import render_markdown


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for a morning_brief config entry."""
    coordinator: MorningBriefCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        MorningBriefSensor(coordinator),
        MorningBriefStatusSensor(coordinator),
        MorningBriefMarkdownSensor(coordinator),
    ]
    # One sensor per configured field — exposes the value + comparisons +
    # anomaly status in HA UI without needing the Lovelace card.
    for field in coordinator.fields:
        field_id = str(field.get("field_id") or field.get("label") or "field")
        entities.append(MorningBriefFieldSensor(coordinator, field_id, field))
    async_add_entities(entities)


def _state_from_data(data: dict[str, Any] | None) -> str:
    """Map canonical brief → main sensor state."""
    if data is None:
        return SENSOR_STATE_NO_DATA
    return str(data.get("meta", {}).get("ai_status", SENSOR_STATE_OK))


def _truncate_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """Return attributes that fit under HA's per-entity attribute limit (D18)."""
    try:
        size = len(json.dumps(data, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        size = SENSOR_ATTRIBUTE_BYTE_LIMIT + 1  # force truncation on weird payloads
    if size <= SENSOR_ATTRIBUTE_BYTE_LIMIT:
        return {**data, "_truncated": False}
    return {
        "meta": data.get("meta"),
        "alerts": data.get("alerts"),
        "previous_briefs_refs": data.get("previous_briefs_refs"),
        "_truncated": True,
    }


def _find_field_in_brief(
    brief: dict[str, Any] | None, field_id: str
) -> dict[str, Any] | None:
    """Look up a field by id in the canonical brief's categories."""
    if brief is None:
        return None
    for category in brief.get("categories", []) or []:
        for field in category.get("fields", []) or []:
            if str(field.get("field_id") or field.get("id") or "") == field_id:
                return field  # type: ignore[no-any-return]
    return None


class MorningBriefSensor(CoordinatorEntity[MorningBriefCoordinator], SensorEntity):
    """Main sensor — exposes the canonical JSON in attributes."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MorningBriefCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_main"
        self._attr_name = coordinator.instance_name or "Morning Brief"
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str:
        return _state_from_data(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {"_truncated": False}
        return _truncate_attributes(self.coordinator.data)


class MorningBriefStatusSensor(
    CoordinatorEntity[MorningBriefCoordinator], SensorEntity
):
    """Lightweight status sensor — never carries the full payload."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MorningBriefCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_status"
        self._attr_name = f"{coordinator.instance_name or 'Morning Brief'} status"
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str:
        return _state_from_data(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {}
        meta = data.get("meta", {}) or {}
        return {
            "last_generation_iso": meta.get("generated_at"),
            "logical_date": meta.get("logical_date"),
            "ai_status": meta.get("ai_status"),
            "ai_provider": meta.get("ai_provider"),
            "brief_count": len(data.get("previous_briefs_refs") or []) + 1,
        }


class MorningBriefMarkdownSensor(
    CoordinatorEntity[MorningBriefCoordinator], SensorEntity
):
    """Renders the canonical brief as markdown in the state attribute.

    State is a short summary (instance_name + logical_date) to fit the
    255-char limit; the full markdown lives in the ``markdown``
    attribute, viewable via Developer Tools → States.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: MorningBriefCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_markdown"
        self._attr_name = (
            f"{coordinator.instance_name or 'Morning Brief'} markdown"
        )
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str:
        data = self.coordinator.data
        if data is None:
            return SENSOR_STATE_NO_DATA
        meta = data.get("meta", {}) or {}
        return f"{meta.get('instance_name', 'Brief')} — {meta.get('logical_date', '')}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {"markdown": ""}
        try:
            return {"markdown": render_markdown(data)}
        except Exception:  # noqa: BLE001 — never crash the entity on a bad brief
            return {"markdown": "_(failed to render — check logs)_"}


class MorningBriefFieldSensor(
    CoordinatorEntity[MorningBriefCoordinator], SensorEntity
):
    """One sensor per configured field — exposes its formatted value.

    Attributes carry comparisons and anomaly info so the user can build
    automations or dashboards directly off these per-field sensors.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MorningBriefCoordinator,
        field_id: str,
        field_config: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._field_id = field_id
        self._attr_unique_id = f"{coordinator.entry_id}_field_{field_id}"
        label = str(field_config.get("label") or field_id)
        self._attr_name = label
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str:
        field = _find_field_in_brief(self.coordinator.data, self._field_id)
        if field is None:
            return SENSOR_STATE_NO_DATA
        value = field.get("value", {}) or {}
        return str(value.get("formatted") or value.get("raw") or SENSOR_STATE_NO_DATA)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        field = _find_field_in_brief(self.coordinator.data, self._field_id)
        if field is None:
            return {}
        value = field.get("value", {}) or {}
        return {
            "raw_value": value.get("raw"),
            "unit": field.get("unit"),
            "stale": value.get("stale", False),
            "stale_reason": value.get("stale_reason"),
            "comparisons": field.get("comparisons", []),
            "anomaly": field.get("anomaly"),
            "icon": field.get("icon"),
            "category_id": field.get("category_id"),
        }


def _device_info(coordinator: MorningBriefCoordinator) -> DeviceInfo:
    """Single device per morning_brief instance (matches button.py)."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry_id)},
        name=coordinator.instance_name or "Morning Brief",
        manufacturer="Morning Brief",
        model=coordinator.report_type,
        entry_type=None,
    )
