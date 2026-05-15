"""Logical-day section schema (Section 20, morning only)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from ..const import (
    DEFAULT_CUTOFF_HOUR,
    DEFAULT_HARD_FALLBACK_HOUR,
    LOGICAL_DAY_FIXED_CUTOFF,
    LOGICAL_DAY_STRATEGIES,
)


def logical_day_schema(current: dict[str, Any]) -> vol.Schema:
    prev = current.get("logical_day", {})
    return vol.Schema(
        {
            vol.Optional(
                "strategy", default=prev.get("strategy", LOGICAL_DAY_FIXED_CUTOFF)
            ): vol.In(list(LOGICAL_DAY_STRATEGIES)),
            vol.Optional(
                "cutoff_hour", default=prev.get("cutoff_hour", DEFAULT_CUTOFF_HOUR)
            ): vol.All(int, vol.Range(min=0, max=23)),
            vol.Optional(
                "sleep_sensor_entity", default=prev.get("sleep_sensor_entity", "")
            ): str,
            vol.Optional("awake_state", default=prev.get("awake_state", "off")): str,
            vol.Optional(
                "hard_fallback_hour",
                default=prev.get("hard_fallback_hour", DEFAULT_HARD_FALLBACK_HOUR),
            ): vol.All(int, vol.Range(min=0, max=23)),
        }
    )
