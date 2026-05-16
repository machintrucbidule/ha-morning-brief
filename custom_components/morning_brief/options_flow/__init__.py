# rationale: HA's OptionsFlow is one class — multiple files defining
# step methods would force mixin gymnastics. The eight sections from
# Section 20 are kept as methods on a single class here; their schemas
# live in the per-section sibling files for readability + testability.
"""Options-flow handler (Section 20).

Main menu lists 8 sections; each routes to a specific step.

Persistence model
-----------------
Sections that mirror initial config_flow fields (``general``,
``logical_day``, ``trigger``) write directly into ``entry.data`` via
``hass.config_entries.async_update_entry(data=...)``. This keeps the
runtime read path simple (it already reads from ``entry.data``) and
avoids a parallel ``entry.options`` shadow tree that would need its own
merge logic in the coordinator.

Sections that do not exist in initial config_flow (``notification``,
``persistence``, ``advanced``, ``reorder_*``) live under
``entry.options.<section>``.

Each step writes its change and returns the user to the main menu —
they can edit several sections in one open without re-launching the
dialog. The ``done`` menu option closes the dialog cleanly.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from ..const import (
    DEFAULT_CUTOFF_HOUR,
    DEFAULT_FALLBACK_HOUR,
    DEFAULT_HARD_FALLBACK_HOUR,
    DEFAULT_RETENTION,
    DEFAULT_SENSOR_BASED_DELAY_MINUTES,
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
    "done",
)


class MorningBriefOptionsFlow(config_entries.OptionsFlow):
    """8-section options flow.

    HA Core ≥ 2024.12 made ``OptionsFlow.config_entry`` a read-only
    property injected by the flow manager via ``self._config_entry``;
    assigning it from a custom ``__init__`` raises AttributeError.
    """

    # ------------------------------------------------------------------ #
    # Initial values helpers — reconstruct each section's "current" dict
    # by reading entry.data (for sections that mirror the config_flow)
    # plus entry.options (for the rest).
    # ------------------------------------------------------------------ #

    def _initial_general(self) -> dict[str, Any]:
        data = dict(self.config_entry.data or {})
        ai = data.get("ai", {}) or {}
        ai_cfg = ai.get("config", {}) or {}
        return {
            "instance_name": data.get("instance_name", ""),
            "language": data.get("language", "en"),
            "ai_provider_type": ai.get("provider_type", "disabled"),
            "ai_entity_id": ai_cfg.get("entity_id", ""),
            "ai_api_key": ai_cfg.get("api_key", ""),
            "ai_model": ai_cfg.get("model", ""),
        }

    def _initial_logical_day(self) -> dict[str, Any]:
        ld = dict((self.config_entry.data or {}).get("logical_day", {}) or {})
        cfg = ld.get("config", {}) or {}
        return {
            "strategy": ld.get("strategy", "fixed_cutoff"),
            "cutoff_hour": cfg.get("cutoff_hour", DEFAULT_CUTOFF_HOUR),
            "sleep_sensor_entity": cfg.get("sleep_sensor_entity", ""),
            "awake_state": cfg.get("awake_state", "off"),
            "hard_fallback_hour": cfg.get("hard_fallback_hour", DEFAULT_HARD_FALLBACK_HOUR),
        }

    def _initial_trigger(self) -> dict[str, Any]:
        tr = dict((self.config_entry.data or {}).get("trigger", {}) or {})
        cfg = tr.get("config", {}) or {}
        return {
            "trigger_level": tr.get("level", "schedule"),
            "time": cfg.get("time", "07:30"),
            "trigger_entity_id": cfg.get("trigger_entity_id", ""),
            "trigger_to_state": cfg.get("trigger_to_state", "off"),
            "delay_minutes": cfg.get(
                "delay_minutes", DEFAULT_SENSOR_BASED_DELAY_MINUTES
            ),
            "fallback_hour": cfg.get("fallback_hour", DEFAULT_FALLBACK_HOUR),
        }

    def _initial_option_section(self, section: str) -> dict[str, Any]:
        return dict((self.config_entry.options or {}).get(section, {}) or {})

    def _is_morning(self) -> bool:
        return self.config_entry.data.get("report_type") == REPORT_TYPE_MORNING

    # ------------------------------------------------------------------ #
    # Persisting helpers
    # ------------------------------------------------------------------ #

    def _save_to_data(self, **updates: Any) -> None:
        """Patch ``entry.data`` with ``updates`` (shallow merge)."""
        new_data = dict(self.config_entry.data or {})
        new_data.update(updates)
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )

    def _save_to_options(self, section: str, payload: dict[str, Any]) -> None:
        """Patch ``entry.options[section]`` with ``payload``."""
        new_opts = dict(self.config_entry.options or {})
        new_opts[section] = payload
        self.hass.config_entries.async_update_entry(
            self.config_entry, options=new_opts
        )

    # ------------------------------------------------------------------ #
    # Main menu
    # ------------------------------------------------------------------ #

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the main menu with all available sections."""
        sections = list(_MENU_SECTIONS_ALWAYS)
        if self._is_morning():
            sections.insert(1, "logical_day")
        return self.async_show_menu(step_id="init", menu_options=sections)

    # Each section step:
    # - On user_input None: show the form with current values pre-filled
    # - On user_input set: persist + return to the menu

    # ------------------------------------------------------------------ #
    # General — writes to entry.data (initial_name/language/AI)
    # ------------------------------------------------------------------ #

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_general(user_input)
            return await self.async_step_init()
        return self.async_show_form(
            step_id="general",
            data_schema=general_schema(self._initial_general()),
        )

    def _save_general(self, payload: dict[str, Any]) -> None:
        ai_provider = payload.get("ai_provider_type", "disabled")
        ai_cfg: dict[str, Any] = {}
        if entity_id := payload.get("ai_entity_id"):
            ai_cfg["entity_id"] = entity_id
        if api_key := payload.get("ai_api_key"):
            ai_cfg["api_key"] = api_key
        if model := payload.get("ai_model"):
            ai_cfg["model"] = model
        self._save_to_data(
            instance_name=payload.get("instance_name") or self.config_entry.data.get("instance_name", ""),
            language=payload.get("language", "en"),
            ai={"provider_type": ai_provider, "config": ai_cfg},
        )

    # ------------------------------------------------------------------ #
    # Logical day (morning only) — writes to entry.data["logical_day"]
    # ------------------------------------------------------------------ #

    async def async_step_logical_day(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            strategy = user_input.pop("strategy", "fixed_cutoff")
            self._save_to_data(
                logical_day={"strategy": strategy, "config": dict(user_input)}
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="logical_day",
            data_schema=logical_day_schema(self._initial_logical_day()),
        )

    # ------------------------------------------------------------------ #
    # Trigger — writes to entry.data["trigger"]
    # ------------------------------------------------------------------ #

    async def async_step_trigger(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            level = user_input.pop("trigger_level", "schedule")
            self._save_to_data(
                trigger={"level": level, "config": dict(user_input)}
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="trigger",
            data_schema=trigger_schema(self._initial_trigger()),
        )

    # ------------------------------------------------------------------ #
    # Notification — writes to entry.options["notification"]
    # ------------------------------------------------------------------ #

    async def async_step_notification(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_options("notification", user_input)
            return await self.async_step_init()
        return self.async_show_form(
            step_id="notification",
            data_schema=notification_schema(self._initial_option_section("notification")),
        )

    # ------------------------------------------------------------------ #
    # Persistence — writes to entry.options["persistence"]
    # ------------------------------------------------------------------ #

    async def async_step_persistence(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            retention = int(user_input.get("retention", DEFAULT_RETENTION))
            retention = max(MIN_RETENTION, min(MAX_RETENTION, retention))
            self._save_to_options("persistence", {"retention": retention})
            return await self.async_step_init()
        return self.async_show_form(
            step_id="persistence",
            data_schema=persistence_schema(self._initial_option_section("persistence")),
        )

    # ------------------------------------------------------------------ #
    # Reorder fields / categories
    # ------------------------------------------------------------------ #

    async def async_step_reorder_fields(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_options("reorder_fields", user_input)
            return await self.async_step_init()
        return self.async_show_form(
            step_id="reorder_fields",
            data_schema=reorder_fields_schema(self.config_entry),
            description_placeholders={"count": str(self._count_subentries("field"))},
        )

    async def async_step_reorder_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_options("reorder_categories", user_input)
            return await self.async_step_init()
        return self.async_show_form(
            step_id="reorder_categories",
            data_schema=reorder_categories_schema(self.config_entry),
            description_placeholders={
                "count": str(self._count_subentries("category"))
            },
        )

    def _count_subentries(self, subentry_type: str) -> int:
        subs = getattr(self.config_entry, "subentries", {}) or {}
        items = list(subs.values()) if isinstance(subs, dict) else list(subs)
        return sum(
            1 for s in items if getattr(s, "subentry_type", None) == subentry_type
        )

    # ------------------------------------------------------------------ #
    # Advanced — writes to entry.options["advanced"]
    # ------------------------------------------------------------------ #

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_options("advanced", user_input)
            return await self.async_step_init()
        return self.async_show_form(
            step_id="advanced",
            data_schema=advanced_schema(self._initial_option_section("advanced")),
        )

    # ------------------------------------------------------------------ #
    # Done — close the dialog cleanly
    # ------------------------------------------------------------------ #

    async def async_step_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """No-op step that finalises the options flow.

        Each section already persisted its changes via async_update_entry,
        so we just need a clean exit. We call async_create_entry with the
        current options dict to satisfy HA's flow lifecycle.
        """
        return self.async_create_entry(
            title="", data=dict(self.config_entry.options or {})
        )


__all__ = ["MorningBriefOptionsFlow"]
