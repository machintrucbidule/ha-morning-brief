"""Advanced section schema (Section 20.1)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def advanced_schema(current: dict[str, Any]) -> vol.Schema:
    prev = current.get("advanced", {})
    return vol.Schema(
        {
            vol.Optional(
                "log_level", default=prev.get("log_level", "INFO")
            ): vol.In(list(_LOG_LEVELS)),
            vol.Optional(
                "prompt_template_override",
                default=prev.get("prompt_template_override", ""),
            ): str,
            vol.Optional(
                "user_custom_context",
                default=prev.get("user_custom_context", ""),
            ): str,
            vol.Optional(
                "expose_preview_service",
                default=prev.get("expose_preview_service", True),
            ): bool,
        }
    )
