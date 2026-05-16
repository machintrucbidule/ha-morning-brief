"""Sensor entities for the morning_brief integration (Section 18.1).

Two sensors per instance:
- ``sensor.morning_brief_<slug>`` — main sensor. State = ai_status enum.
  Attributes = the full canonical JSON (Section 15), or a truncated
  ``{meta, alerts, previous_briefs_refs, _truncated: true}`` slice when
  the full payload exceeds ``SENSOR_ATTRIBUTE_BYTE_LIMIT`` (D18, G13).
- ``sensor.morning_brief_<slug>_status`` — lightweight status sensor.
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for a morning_brief config entry."""
    coordinator: MorningBriefCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [MorningBriefSensor(coordinator), MorningBriefStatusSensor(coordinator)]
    )


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


class MorningBriefSensor(CoordinatorEntity[MorningBriefCoordinator], SensorEntity):
    """Main sensor — exposes the canonical JSON in attributes."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MorningBriefCoordinator) -> None:
        """Bind to its coordinator."""
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


class MorningBriefStatusSensor(CoordinatorEntity[MorningBriefCoordinator], SensorEntity):
    """Lightweight status sensor — never carries the full payload."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MorningBriefCoordinator) -> None:
        """Bind to its coordinator."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_status"
        self._attr_name = f"{coordinator.instance_name or 'Morning Brief'} status"
        self._attr_device_info = _device_info(coordinator)


def _device_info(coordinator: MorningBriefCoordinator) -> DeviceInfo:
    """Single device per morning_brief instance (matches button.py)."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry_id)},
        name=coordinator.instance_name or "Morning Brief",
        manufacturer="Morning Brief",
        model=coordinator.report_type,
        entry_type=None,
    )

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
        }
