"""Trigger section schema (Section 20)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

from ..const import (
    DEFAULT_FALLBACK_HOUR,
    DEFAULT_SENSOR_BASED_DELAY_MINUTES,
    TRIGGER_LEVELS,
    TRIGGER_SCHEDULE,
)


def trigger_schema(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "trigger_level",
                default=initial.get("trigger_level", TRIGGER_SCHEDULE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(TRIGGER_LEVELS),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="trigger_level",
                )
            ),
            vol.Optional(
                "time", default=initial.get("time", "07:30")
            ): selector.TimeSelector(),
            vol.Optional(
                "trigger_entity_id",
                default=initial.get("trigger_entity_id", ""),
            ): selector.EntitySelector(selector.EntitySelectorConfig()),
            vol.Optional(
                "trigger_to_state",
                default=initial.get("trigger_to_state", "off"),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "delay_minutes",
                default=initial.get(
                    "delay_minutes", DEFAULT_SENSOR_BASED_DELAY_MINUTES
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=240, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "fallback_hour",
                default=initial.get("fallback_hour", DEFAULT_FALLBACK_HOUR),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )
