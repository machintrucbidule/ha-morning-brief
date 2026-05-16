"""General-section schema for the options flow (Section 20.1)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

from ..const import AI_PROVIDER_TYPES, SUPPORTED_LANGUAGES


def general_schema(initial: dict[str, Any]) -> vol.Schema:
    """Rename instance + change language + swap AI provider type/key.

    ``initial`` carries the current values for each field (already
    flattened by the flow handler — reads from entry.data).
    """
    return vol.Schema(
        {
            vol.Required(
                "instance_name", default=initial.get("instance_name", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(
                "language", default=initial.get("language", "en")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(SUPPORTED_LANGUAGES),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="language",
                )
            ),
            vol.Required(
                "ai_provider_type", default=initial.get("ai_provider_type", "disabled")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(AI_PROVIDER_TYPES),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="ai_provider_type",
                )
            ),
            vol.Optional(
                "ai_entity_id", default=initial.get("ai_entity_id", "")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="ai_task")
            ),
            vol.Optional(
                "ai_api_key", default=initial.get("ai_api_key", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                "ai_model", default=initial.get("ai_model", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )
