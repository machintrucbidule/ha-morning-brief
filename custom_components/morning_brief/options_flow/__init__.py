# rationale: HA's OptionsFlow is one class — multiple files defining
# step methods would force mixin gymnastics. The eight sections from
# Section 20 are kept as methods on a single class here; their schemas
# live in the per-section sibling files for readability + testability.
"""Options-flow handler (Section 20).

Main menu lists 8 sections; each routes to a specific step that
updates the entry's options. Schemas live in
``options_flow/<section>.py`` for clarity.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from ..const import (
    DEFAULT_RETENTION,
    MAX_RETENTION,
    MIN_RETENTION,
    REPORT_TYPE_MORNING,
)
from .advanced import advanced_schema
from .general import general_schema
from .logical_day import logical_day_schema
from .notification import notification_schema
from .persistence import persistence_schema
from .reorder import reorder_categories_schema, reorder_fields_schema
from .trigger import trigger_schema

_LOGGER = logging.getLogger(__name__)

_MENU_SECTIONS_ALWAYS = (
    "general",
    "trigger",
    "notification",
    "persistence",
    "reorder_fields",
    "reorder_categories",
    "advanced",
)


class MorningBriefOptionsFlow(config_entries.OptionsFlow):
    """8-section options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Capture the entry; we read its current options for form defaults."""
        self.config_entry = config_entry

    @property
    def _current_options(self) -> dict[str, Any]:
        return dict(self.config_entry.options or {})

    def _is_morning(self) -> bool:
        return self.config_entry.data.get("report_type") == REPORT_TYPE_MORNING

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the main menu with all available sections."""
        sections = list(_MENU_SECTIONS_ALWAYS)
        if self._is_morning():
            sections.insert(1, "logical_day")
        return self.async_show_menu(step_id="init", menu_options=sections)

    # ------------------------------------------------------------------ #
    # General
    # ------------------------------------------------------------------ #

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save_section("general", user_input)
        return self.async_show_form(
            step_id="general",
            data_schema=general_schema(self._current_options),
        )

    # ------------------------------------------------------------------ #
    # Logical day (morning only)
    # ------------------------------------------------------------------ #

    async def async_step_logical_day(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save_section("logical_day", user_input)
        return self.async_show_form(
            step_id="logical_day",
            data_schema=logical_day_schema(self._current_options),
        )

    # ------------------------------------------------------------------ #
    # Trigger
    # ------------------------------------------------------------------ #

    async def async_step_trigger(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save_section("trigger", user_input)
        return self.async_show_form(
            step_id="trigger",
            data_schema=trigger_schema(self._current_options),
        )

    # ------------------------------------------------------------------ #
    # Notification
    # ------------------------------------------------------------------ #

    async def async_step_notification(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save_section("notification", user_input)
        return self.async_show_form(
            step_id="notification",
            data_schema=notification_schema(self._current_options),
        )

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    async def async_step_persistence(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            retention = int(user_input.get("retention", DEFAULT_RETENTION))
            retention = max(MIN_RETENTION, min(MAX_RETENTION, retention))
            user_input["retention"] = retention
            return self._save_section("persistence", user_input)
        return self.async_show_form(
            step_id="persistence",
            data_schema=persistence_schema(self._current_options),
        )

    # ------------------------------------------------------------------ #
    # Reorder fields / categories
    # ------------------------------------------------------------------ #

    async def async_step_reorder_fields(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        # Reorder is a Section 22 numeric-order form. The actual write to
        # subentries happens in Phase 9 via the reorder_fields service.
        if user_input is not None:
            return self._save_section("reorder_fields", user_input)
        return self.async_show_form(
            step_id="reorder_fields",
            data_schema=reorder_fields_schema(self.config_entry),
        )

    async def async_step_reorder_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save_section("reorder_categories", user_input)
        return self.async_show_form(
            step_id="reorder_categories",
            data_schema=reorder_categories_schema(self.config_entry),
        )

    # ------------------------------------------------------------------ #
    # Advanced
    # ------------------------------------------------------------------ #

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save_section("advanced", user_input)
        return self.async_show_form(
            step_id="advanced",
            data_schema=advanced_schema(self._current_options),
        )

    # ------------------------------------------------------------------ #
    # Shared save logic
    # ------------------------------------------------------------------ #

    def _save_section(self, section: str, payload: dict[str, Any]) -> ConfigFlowResult:
        """Merge ``payload`` into the entry's options under ``section``."""
        opts = dict(self._current_options)
        opts[section] = payload
        return self.async_create_entry(title="", data=opts)


__all__ = ["MorningBriefOptionsFlow"]

# Re-export schema helpers for tests.
_ = (
    vol,
    advanced_schema,
    general_schema,
    logical_day_schema,
    notification_schema,
    persistence_schema,
    reorder_categories_schema,
    reorder_fields_schema,
    trigger_schema,
)
