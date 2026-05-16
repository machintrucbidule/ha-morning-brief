"""Notification section schema (Section 20, D19)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector


def notification_schema(initial: dict[str, Any]) -> vol.Schema:
    """Where to send the brief + how to make it clickable.

    ``initial`` carries the current values for each field (read from
    entry.options.notification by the flow handler).
    """
    return vol.Schema(
        {
            vol.Optional(
                "notify_service", default=initial.get("notify_service", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "click_action_url", default=initial.get("click_action_url", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            vol.Optional(
                "notification_pinned_fields",
                default=initial.get("notification_pinned_fields", ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "also_create_persistent_notification",
                default=initial.get(
                    "also_create_persistent_notification", False
                ),
            ): selector.BooleanSelector(),
        }
    )
