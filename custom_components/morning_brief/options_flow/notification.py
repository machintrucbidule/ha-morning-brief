"""Notification section schema (Section 20, D19)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol


def notification_schema(current: dict[str, Any]) -> vol.Schema:
    prev = current.get("notification", {})
    return vol.Schema(
        {
            vol.Optional(
                "notify_service", default=prev.get("notify_service", "")
            ): str,
            vol.Optional(
                "click_action_url", default=prev.get("click_action_url", "")
            ): str,
            vol.Optional(
                "notification_pinned_fields",
                default=prev.get("notification_pinned_fields", []),
            ): [str],
            vol.Optional(
                "also_create_persistent_notification",
                default=prev.get("also_create_persistent_notification", False),
            ): bool,
        }
    )
