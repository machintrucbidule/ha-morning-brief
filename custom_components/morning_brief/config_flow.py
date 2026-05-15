# rationale: the 6-step initial config flow per MORNING_BRIEF_SPEC.md
# Section 19 is naturally cohesive — each step branches conditionally
# off the report_type / strategy / trigger / ai_provider choice. Splitting
# would scatter the assembled `_draft` state across files.
"""Initial config flow for the morning_brief integration.

See MORNING_BRIEF_SPEC.md Section 19. Six linear steps:

1. ``user`` — choose report_type (morning / evening / weekly).
2. ``name_lang`` — instance name + language.
3. ``logical_day`` — strategy + params (morning only; skipped otherwise).
4. ``trigger`` — trigger level + params.
5. ``ai`` — AI provider type + credentials.
6. ``copy_from`` — optional one-shot copy of fields/categories from an
   existing instance.

The flow accumulates a `_draft` dict and creates the config entry on the
final step. Subentries (fields + categories) are added afterwards by
the user via the native HA subentry UI (Phase 8 also ships those flows).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

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


def _trigger_schema(trigger_level: str) -> vol.Schema:
    """Build the voluptuous schema for the chosen trigger level.

    All schemas allow extra keys (``vol.REMOVE_EXTRA``): the conditional
    one-screen forms ship the union of fields, and we only keep what's
    relevant per the chosen enum.
    """
    if trigger_level == TRIGGER_SCHEDULE:
        return vol.Schema(
            {
                vol.Required("time", default="07:30"): vol.Match(r"^\d{1,2}:\d{2}$"),
                vol.Optional("days_of_week", default=list(range(7))): [
                    vol.All(int, vol.Range(min=0, max=6))
                ],
            },
            extra=vol.REMOVE_EXTRA,
        )
    if trigger_level == TRIGGER_SENSOR_BASED:
        return vol.Schema(
            {
                vol.Required("trigger_entity_id"): str,
                vol.Required("trigger_to_state"): str,
                vol.Optional(
                    "delay_minutes", default=DEFAULT_SENSOR_BASED_DELAY_MINUTES
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional("optout_entities", default=list): [str],
                vol.Optional(
                    "fallback_hour", default=DEFAULT_FALLBACK_HOUR
                ): vol.All(int, vol.Range(min=0, max=23)),
                vol.Optional("fallback_active", default=True): bool,
            },
            extra=vol.REMOVE_EXTRA,
        )
    return vol.Schema({}, extra=vol.REMOVE_EXTRA)


def _logical_day_schema(strategy: str) -> vol.Schema:
    if strategy == LOGICAL_DAY_FIXED_CUTOFF:
        return vol.Schema(
            {
                vol.Optional("cutoff_hour", default=DEFAULT_CUTOFF_HOUR): vol.All(
                    int, vol.Range(min=0, max=23)
                ),
            },
            extra=vol.REMOVE_EXTRA,
        )
    if strategy == LOGICAL_DAY_SLEEP_SENSOR:
        return vol.Schema(
            {
                vol.Required("sleep_sensor_entity"): str,
                vol.Optional("awake_state", default="off"): str,
                vol.Optional(
                    "hard_fallback_hour", default=DEFAULT_HARD_FALLBACK_HOUR
                ): vol.All(int, vol.Range(min=0, max=23)),
                vol.Optional("lookback_hours", default=DEFAULT_LOOKBACK_HOURS): vol.All(
                    int, vol.Range(min=1, max=72)
                ),
                vol.Optional(
                    "min_sleep_duration_minutes",
                    default=DEFAULT_MIN_SLEEP_DURATION_MINUTES,
                ): vol.All(int, vol.Range(min=0)),
            },
            extra=vol.REMOVE_EXTRA,
        )
    return vol.Schema({}, extra=vol.REMOVE_EXTRA)


def _ai_schema(provider_type: str) -> vol.Schema:
    if provider_type == AI_PROVIDER_HA_AI_TASK:
        return vol.Schema(
            {vol.Required("entity_id"): str}, extra=vol.REMOVE_EXTRA
        )
    if provider_type == AI_PROVIDER_ANTHROPIC_DIRECT:
        return vol.Schema(
            {
                vol.Required("api_key"): str,
                vol.Optional("model", default="claude-sonnet-4-7"): str,
            },
            extra=vol.REMOVE_EXTRA,
        )
    if provider_type == AI_PROVIDER_OPENAI_DIRECT:
        return vol.Schema(
            {
                vol.Required("api_key"): str,
                vol.Optional("model", default="gpt-4o-mini"): str,
            },
            extra=vol.REMOVE_EXTRA,
        )
    return vol.Schema({}, extra=vol.REMOVE_EXTRA)


class MorningBriefConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Six-step flow that produces a `morning_brief` config entry."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise an empty draft."""
        self._draft: dict[str, Any] = {}

    # ------------------------------------------------------------------- #
    # Step 1 — Report type
    # ------------------------------------------------------------------- #

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Initial step: choose report_type."""
        if user_input is not None:
            self._draft["report_type"] = user_input["report_type"]
            return await self.async_step_name_lang()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("report_type"): vol.In(list(REPORT_TYPES))}
            ),
        )

    # ------------------------------------------------------------------- #
    # Step 2 — Name + language
    # ------------------------------------------------------------------- #

    async def async_step_name_lang(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._draft["instance_name"] = user_input["instance_name"]
            self._draft["language"] = user_input["language"]
            if self._draft["report_type"] == REPORT_TYPE_MORNING:
                return await self.async_step_logical_day()
            return await self.async_step_trigger()
        return self.async_show_form(
            step_id="name_lang",
            data_schema=vol.Schema(
                {
                    vol.Required("instance_name"): str,
                    vol.Optional(
                        "language",
                        default=str(self.hass.config.language or DEFAULT_LANGUAGE),
                    ): vol.In(list(SUPPORTED_LANGUAGES)),
                }
            ),
        )

    # ------------------------------------------------------------------- #
    # Step 3 — Logical day strategy (morning only)
    # ------------------------------------------------------------------- #

    async def async_step_logical_day(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None and "strategy" in user_input:
            strategy = user_input["strategy"]
            # On the second submit, validate the strategy-specific params.
            params = {k: v for k, v in user_input.items() if k != "strategy"}
            try:
                params = _logical_day_schema(strategy)(params)
            except vol.Invalid as err:
                return self.async_show_form(
                    step_id="logical_day",
                    data_schema=self._logical_day_form_schema(strategy),
                    errors={"base": str(err)},
                )
            self._draft["logical_day"] = {"strategy": strategy, "config": params}
            return await self.async_step_trigger()
        return self.async_show_form(
            step_id="logical_day",
            data_schema=self._logical_day_form_schema(LOGICAL_DAY_FIXED_CUTOFF),
        )

    @staticmethod
    def _logical_day_form_schema(default_strategy: str) -> vol.Schema:
        """One screen with strategy + all-possible params (validated conditionally)."""
        return vol.Schema(
            {
                vol.Required("strategy", default=default_strategy): vol.In(
                    list(LOGICAL_DAY_STRATEGIES)
                ),
                vol.Optional("cutoff_hour", default=DEFAULT_CUTOFF_HOUR): vol.All(
                    int, vol.Range(min=0, max=23)
                ),
                vol.Optional("sleep_sensor_entity", default=""): str,
                vol.Optional("awake_state", default="off"): str,
                vol.Optional(
                    "hard_fallback_hour", default=DEFAULT_HARD_FALLBACK_HOUR
                ): vol.All(int, vol.Range(min=0, max=23)),
                vol.Optional("lookback_hours", default=DEFAULT_LOOKBACK_HOURS): vol.All(
                    int, vol.Range(min=1, max=72)
                ),
                vol.Optional(
                    "min_sleep_duration_minutes",
                    default=DEFAULT_MIN_SLEEP_DURATION_MINUTES,
                ): vol.All(int, vol.Range(min=0)),
            }
        )

    # ------------------------------------------------------------------- #
    # Step 4 — Trigger
    # ------------------------------------------------------------------- #

    async def async_step_trigger(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None and "trigger_level" in user_input:
            level = user_input["trigger_level"]
            params = {k: v for k, v in user_input.items() if k != "trigger_level"}
            if level == TRIGGER_EXTERNAL:
                params = {}
            self._draft["trigger"] = {"level": level, "config": params}
            return await self.async_step_ai()
        return self.async_show_form(
            step_id="trigger",
            data_schema=vol.Schema(
                {
                    vol.Required("trigger_level", default=TRIGGER_SCHEDULE): vol.In(
                        list(TRIGGER_LEVELS)
                    ),
                    vol.Optional("time", default="07:30"): str,
                    vol.Optional("trigger_entity_id", default=""): str,
                    vol.Optional("trigger_to_state", default="off"): str,
                    vol.Optional(
                        "delay_minutes", default=DEFAULT_SENSOR_BASED_DELAY_MINUTES
                    ): vol.All(int, vol.Range(min=0)),
                    vol.Optional("fallback_hour", default=DEFAULT_FALLBACK_HOUR): vol.All(
                        int, vol.Range(min=0, max=23)
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------- #
    # Step 5 — AI provider
    # ------------------------------------------------------------------- #

    async def async_step_ai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None and "ai_provider_type" in user_input:
            ptype = user_input["ai_provider_type"]
            cfg: dict[str, Any] = {k: v for k, v in user_input.items() if k != "ai_provider_type"}
            try:
                cfg = _ai_schema(ptype)(
                    {k: v for k, v in cfg.items() if v not in (None, "")}
                )
            except vol.Invalid as err:
                return self.async_show_form(
                    step_id="ai",
                    data_schema=self._ai_form_schema(),
                    errors={"base": str(err)},
                )
            self._draft["ai"] = {"provider_type": ptype, "config": cfg}
            return await self.async_step_copy_from()
        return self.async_show_form(
            step_id="ai", data_schema=self._ai_form_schema()
        )

    @staticmethod
    def _ai_form_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("ai_provider_type", default=AI_PROVIDER_DISABLED): vol.In(
                    list(AI_PROVIDER_TYPES)
                ),
                vol.Optional("entity_id", default=""): str,
                vol.Optional("api_key", default=""): str,
                vol.Optional("model", default=""): str,
            }
        )

    # ------------------------------------------------------------------- #
    # Step 6 — Copy from existing
    # ------------------------------------------------------------------- #

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
                    ): vol.In(choices),
                }
            ),
        )

    # ------------------------------------------------------------------- #
    # Options flow registration
    # ------------------------------------------------------------------- #

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
