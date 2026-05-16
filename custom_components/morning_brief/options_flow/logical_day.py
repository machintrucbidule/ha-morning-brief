"""Logical-day section schema (Section 20, morning only)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

from ..const import (
    DEFAULT_CUTOFF_HOUR,
    DEFAULT_HARD_FALLBACK_HOUR,
    LOGICAL_DAY_FIXED_CUTOFF,
    LOGICAL_DAY_STRATEGIES,
)


def logical_day_schema(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "strategy", default=initial.get("strategy", LOGICAL_DAY_FIXED_CUTOFF)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(LOGICAL_DAY_STRATEGIES),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="logical_day_strategy",
                )
            ),
            vol.Optional(
                "cutoff_hour", default=initial.get("cutoff_hour", DEFAULT_CUTOFF_HOUR)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "sleep_sensor_entity",
                default=initial.get("sleep_sensor_entity", ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(
                "awake_state", default=initial.get("awake_state", "off")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "hard_fallback_hour",
                default=initial.get("hard_fallback_hour", DEFAULT_HARD_FALLBACK_HOUR),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )
