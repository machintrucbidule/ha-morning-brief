# rationale: ~330 LOC because each branch step has its own per-strategy
# / per-trigger-level / per-provider form. Splitting would scatter the
# accumulated `_draft` state across many small files without clarity gain.
"""Initial config flow for the morning_brief integration.

See MORNING_BRIEF_SPEC.md Section 19.

The flow is structured as N visible steps, with branching steps:

1. ``user`` — choose report_type.
2. ``name_lang`` — instance name + language.
3. ``logical_day_strategy`` — strategy enum picker (morning only).
4. ``logical_day_<strategy>`` — params for the chosen strategy.
5. ``trigger_level`` — trigger level enum picker.
6. ``trigger_<level>`` — params for the chosen trigger level.
7. ``ai_provider`` — AI provider enum picker.
8. ``ai_<provider>`` — credentials for the chosen provider.
9. ``copy_from`` — optional one-shot copy of fields/categories.

Splitting the enum picker from the param form means each form only
shows fields that are actually relevant — addressing the original UX
bug where the unified "all-fields" form showed inputs that depended on
a choice made on the same screen.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    AI_PROVIDER_ANTHROPIC_DIRECT,
    AI_PROVIDER_DISABLED,
    AI_PROVIDER_HA_AI_TASK,
    AI_PROVIDER_OPENAI_DIRECT,
    AI_PROVIDER_TYPES,
    DEFAULT_CUTOFF_HOUR,
    DEFAULT_FALLBACK_HOUR,
    DEFAULT_HARD_FALLBACK_HOUR,
    DEFAULT_LANGUAGE,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_MIN_SLEEP_DURATION_MINUTES,
    DEFAULT_SENSOR_BASED_DELAY_MINUTES,
    DOMAIN,
    LOGICAL_DAY_FIXED_CUTOFF,
    LOGICAL_DAY_MANUAL,
    LOGICAL_DAY_SLEEP_SENSOR,
    LOGICAL_DAY_STRATEGIES,
    REPORT_TYPE_MORNING,
    REPORT_TYPES,
    SUPPORTED_LANGUAGES,
    TRIGGER_EXTERNAL,
    TRIGGER_LEVELS,
    TRIGGER_SCHEDULE,
    TRIGGER_SENSOR_BASED,
)

_LOGGER = logging.getLogger(__name__)


class MorningBriefConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Multi-step flow that produces a `morning_brief` config entry."""

    VERSION = 1

    def __init__(self) -> None:
        self._draft: dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Step 1 — Report type
    # ------------------------------------------------------------------ #

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["report_type"] = user_input["report_type"]
            return await self.async_step_name_lang()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("report_type"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(REPORT_TYPES),
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="report_type",
                        )
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 2 — Name + language
    # ------------------------------------------------------------------ #

    async def async_step_name_lang(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["instance_name"] = user_input["instance_name"]
            self._draft["language"] = user_input["language"]
            if self._draft["report_type"] == REPORT_TYPE_MORNING:
                return await self.async_step_logical_day_strategy()
            return await self.async_step_trigger_level()
        return self.async_show_form(
            step_id="name_lang",
            data_schema=vol.Schema(
                {
                    vol.Required("instance_name"): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        )
                    ),
                    vol.Required(
                        "language",
                        default=str(self.hass.config.language or DEFAULT_LANGUAGE),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(SUPPORTED_LANGUAGES),
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="language",
                        )
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 3 — Logical-day strategy picker (morning only)
    # ------------------------------------------------------------------ #

    async def async_step_logical_day_strategy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            strategy = user_input["strategy"]
            self._draft["_logical_day_strategy_choice"] = strategy
            if strategy == LOGICAL_DAY_FIXED_CUTOFF:
                return await self.async_step_logical_day_fixed_cutoff()
            if strategy == LOGICAL_DAY_SLEEP_SENSOR:
                return await self.async_step_logical_day_sleep_sensor()
            # manual has no params
            self._draft["logical_day"] = {"strategy": LOGICAL_DAY_MANUAL, "config": {}}
            return await self.async_step_trigger_level()
        return self.async_show_form(
            step_id="logical_day_strategy",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "strategy", default=LOGICAL_DAY_FIXED_CUTOFF
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(LOGICAL_DAY_STRATEGIES),
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="logical_day_strategy",
                        )
                    ),
                }
            ),
        )

    async def async_step_logical_day_fixed_cutoff(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["logical_day"] = {
                "strategy": LOGICAL_DAY_FIXED_CUTOFF,
                "config": dict(user_input),
            }
            return await self.async_step_trigger_level()
        return self.async_show_form(
            step_id="logical_day_fixed_cutoff",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "cutoff_hour", default=DEFAULT_CUTOFF_HOUR
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=23,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_logical_day_sleep_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["logical_day"] = {
                "strategy": LOGICAL_DAY_SLEEP_SENSOR,
                "config": dict(user_input),
            }
            return await self.async_step_trigger_level()
        return self.async_show_form(
            step_id="logical_day_sleep_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required("sleep_sensor_entity"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="binary_sensor")
                    ),
                    vol.Optional(
                        "awake_state", default="off"
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        )
                    ),
                    vol.Optional(
                        "hard_fallback_hour", default=DEFAULT_HARD_FALLBACK_HOUR
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        "lookback_hours", default=DEFAULT_LOOKBACK_HOURS
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=72, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        "min_sleep_duration_minutes",
                        default=DEFAULT_MIN_SLEEP_DURATION_MINUTES,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=600, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 4 — Trigger-level picker
    # ------------------------------------------------------------------ #

    async def async_step_trigger_level(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            level = user_input["trigger_level"]
            self._draft["_trigger_level_choice"] = level
            if level == TRIGGER_SCHEDULE:
                return await self.async_step_trigger_schedule()
            if level == TRIGGER_SENSOR_BASED:
                return await self.async_step_trigger_sensor_based()
            # external — no params
            self._draft["trigger"] = {"level": TRIGGER_EXTERNAL, "config": {}}
            return await self.async_step_ai_provider()
        return self.async_show_form(
            step_id="trigger_level",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "trigger_level", default=TRIGGER_SCHEDULE
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(TRIGGER_LEVELS),
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="trigger_level",
                        )
                    ),
                }
            ),
        )

    async def async_step_trigger_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["trigger"] = {
                "level": TRIGGER_SCHEDULE,
                "config": dict(user_input),
            }
            return await self.async_step_ai_provider()
        return self.async_show_form(
            step_id="trigger_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("time", default="07:30"): selector.TimeSelector(),
                    vol.Optional(
                        "days_of_week", default=list(range(7))
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="0", label="Mon"),
                                selector.SelectOptionDict(value="1", label="Tue"),
                                selector.SelectOptionDict(value="2", label="Wed"),
                                selector.SelectOptionDict(value="3", label="Thu"),
                                selector.SelectOptionDict(value="4", label="Fri"),
                                selector.SelectOptionDict(value="5", label="Sat"),
                                selector.SelectOptionDict(value="6", label="Sun"),
                            ],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_trigger_sensor_based(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["trigger"] = {
                "level": TRIGGER_SENSOR_BASED,
                "config": dict(user_input),
            }
            return await self.async_step_ai_provider()
        return self.async_show_form(
            step_id="trigger_sensor_based",
            data_schema=vol.Schema(
                {
                    vol.Required("trigger_entity_id"): selector.EntitySelector(
                        selector.EntitySelectorConfig()
                    ),
                    vol.Required(
                        "trigger_to_state", default="off"
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        )
                    ),
                    vol.Optional(
                        "delay_minutes",
                        default=DEFAULT_SENSOR_BASED_DELAY_MINUTES,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=240, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        "fallback_hour", default=DEFAULT_FALLBACK_HOUR
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        "fallback_active", default=True
                    ): selector.BooleanSelector(),
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 5 — AI provider picker
    # ------------------------------------------------------------------ #

    async def async_step_ai_provider(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            provider = user_input["ai_provider_type"]
            self._draft["_ai_provider_choice"] = provider
            if provider == AI_PROVIDER_DISABLED:
                self._draft["ai"] = {"provider_type": AI_PROVIDER_DISABLED, "config": {}}
                return await self.async_step_copy_from()
            if provider == AI_PROVIDER_HA_AI_TASK:
                return await self.async_step_ai_ha_ai_task()
            if provider == AI_PROVIDER_ANTHROPIC_DIRECT:
                return await self.async_step_ai_anthropic()
            if provider == AI_PROVIDER_OPENAI_DIRECT:
                return await self.async_step_ai_openai()
            return await self.async_step_copy_from()
        return self.async_show_form(
            step_id="ai_provider",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "ai_provider_type", default=AI_PROVIDER_DISABLED
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(AI_PROVIDER_TYPES),
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="ai_provider_type",
                        )
                    ),
                }
            ),
        )

    async def async_step_ai_ha_ai_task(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["ai"] = {
                "provider_type": AI_PROVIDER_HA_AI_TASK,
                "config": dict(user_input),
            }
            return await self.async_step_copy_from()
        return self.async_show_form(
            step_id="ai_ha_ai_task",
            data_schema=vol.Schema(
                {
                    vol.Required("entity_id"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="ai_task")
                    ),
                }
            ),
        )

    async def async_step_ai_anthropic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["ai"] = {
                "provider_type": AI_PROVIDER_ANTHROPIC_DIRECT,
                "config": dict(user_input),
            }
            return await self.async_step_copy_from()
        return self.async_show_form(
            step_id="ai_anthropic",
            data_schema=vol.Schema(
                {
                    vol.Required("api_key"): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        "model", default="claude-sonnet-4-6"
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        )
                    ),
                }
            ),
        )

    async def async_step_ai_openai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["ai"] = {
                "provider_type": AI_PROVIDER_OPENAI_DIRECT,
                "config": dict(user_input),
            }
            return await self.async_step_copy_from()
        return self.async_show_form(
            step_id="ai_openai",
            data_schema=vol.Schema(
                {
                    vol.Required("api_key"): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        "model", default="gpt-4o-mini"
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        )
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 6 — Copy from existing instance
    # ------------------------------------------------------------------ #

    async def async_step_copy_from(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        existing = [
            entry.entry_id for entry in self.hass.config_entries.async_entries(DOMAIN)
        ]
        if user_input is not None:
            copy_id = user_input.get("copy_from_instance") or None
            if copy_id == "_none_":
                copy_id = None
            self._draft["copy_from_instance"] = copy_id
            # Strip the choice markers we used as ephemeral state.
            self._draft.pop("_logical_day_strategy_choice", None)
            self._draft.pop("_trigger_level_choice", None)
            self._draft.pop("_ai_provider_choice", None)
            return self.async_create_entry(
                title=str(self._draft["instance_name"]), data=self._draft
            )
        choices = ["_none_", *existing]
        return self.async_show_form(
            step_id="copy_from",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "copy_from_instance", default="_none_"
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Options flow registration
    # ------------------------------------------------------------------ #

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Wire the options flow handler (Section 20).

        Per HA Core ≥ 2024.12 the flow manager injects ``config_entry``
        into the OptionsFlow instance as a read-only property; the
        constructor takes no arguments.
        """
        from .options_flow import MorningBriefOptionsFlow

        return MorningBriefOptionsFlow()

    # ------------------------------------------------------------------ #
    # Subentry flows registration (D3, Section 21)
    # ------------------------------------------------------------------ #

    @classmethod
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, Any]:
        """Expose the subentry flow handlers to HA's UI.

        Without this classmethod, HA reads `manifest.json
        supported_subentry_types` but has no mapping to the actual flow
        classes — the "+ Add sub-item" buttons never appear on the
        integration's device page (G22). Required since HA Core ≥ 2024.11.

        Return type is ``dict[str, Any]`` rather than the more precise
        ``dict[str, type[ConfigSubentryFlow]]`` because ``ConfigSubentryFlow``
        is not exposed on HA Core < 2024.11 and we keep a defensive
        TYPE_CHECKING shim in the subentry flow modules.
        """
        from .subentries import SUBENTRY_FLOWS

        return SUBENTRY_FLOWS
