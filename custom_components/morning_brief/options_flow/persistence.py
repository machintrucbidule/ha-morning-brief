"""Persistence section schema (Section 20, D16)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

from ..const import DEFAULT_RETENTION, MAX_RETENTION, MIN_RETENTION


def persistence_schema(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "retention", default=initial.get("retention", DEFAULT_RETENTION)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_RETENTION,
                    max=MAX_RETENTION,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )
