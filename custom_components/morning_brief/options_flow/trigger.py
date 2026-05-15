"""Trigger section schema (Section 20)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from ..const import (
    DEFAULT_FALLBACK_HOUR,
    DEFAULT_SENSOR_BASED_DELAY_MINUTES,
    TRIGGER_LEVELS,
    TRIGGER_SCHEDULE,
)


def trigger_schema(current: dict[str, Any]) -> vol.Schema:
    prev = current.get("trigger", {})
    return vol.Schema(
        {
            vol.Optional(
                "trigger_level", default=prev.get("trigger_level", TRIGGER_SCHEDULE)
            ): vol.In(list(TRIGGER_LEVELS)),
            vol.Optional("time", default=prev.get("time", "07:30")): str,
            vol.Optional(
                "trigger_entity_id", default=prev.get("trigger_entity_id", "")
            ): str,
            vol.Optional(
                "trigger_to_state", default=prev.get("trigger_to_state", "off")
            ): str,
            vol.Optional(
                "delay_minutes",
                default=prev.get("delay_minutes", DEFAULT_SENSOR_BASED_DELAY_MINUTES),
            ): vol.All(int, vol.Range(min=0)),
            vol.Optional(
                "fallback_hour",
                default=prev.get("fallback_hour", DEFAULT_FALLBACK_HOUR),
            ): vol.All(int, vol.Range(min=0, max=23)),
        }
    )
