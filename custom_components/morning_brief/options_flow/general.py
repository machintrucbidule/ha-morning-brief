"""General-section schema for the options flow (Section 20.1)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from ..const import AI_PROVIDER_TYPES, SUPPORTED_LANGUAGES


def general_schema(current: dict[str, Any]) -> vol.Schema:
    """Rename instance + change language + swap AI provider type/key."""
    prev = current.get("general", {})
    return vol.Schema(
        {
            vol.Optional(
                "instance_name", default=prev.get("instance_name", "")
            ): str,
            vol.Optional(
                "language", default=prev.get("language", "en")
            ): vol.In(list(SUPPORTED_LANGUAGES)),
            vol.Optional(
                "ai_provider_type", default=prev.get("ai_provider_type", "disabled")
            ): vol.In(list(AI_PROVIDER_TYPES)),
            vol.Optional("ai_entity_id", default=prev.get("ai_entity_id", "")): str,
            vol.Optional("ai_api_key", default=prev.get("ai_api_key", "")): str,
            vol.Optional("ai_model", default=prev.get("ai_model", "")): str,
        }
    )
