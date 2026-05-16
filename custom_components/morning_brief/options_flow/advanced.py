"""Advanced section schema (Section 20.1)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def advanced_schema(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "log_level", default=initial.get("log_level", "INFO")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(_LOG_LEVELS),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                "prompt_template_override",
                default=initial.get("prompt_template_override", ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT, multiline=True
                )
            ),
            vol.Optional(
                "user_custom_context",
                default=initial.get("user_custom_context", ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT, multiline=True
                )
            ),
            vol.Required(
                "expose_preview_service",
                default=initial.get("expose_preview_service", True),
            ): selector.BooleanSelector(),
        }
    )
