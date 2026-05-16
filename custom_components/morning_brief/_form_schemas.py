# rationale: 200+ LOC because we host one schema function per
# branch-step (logical_day × 2, trigger × 2, ai × 3) plus the picker
# schemas (logical_day_strategy, trigger_level, ai_provider). Keeping
# them in one file avoids 7 sibling modules of ~30 lines each.
"""Voluptuous schemas shared between the initial config_flow and the
options_flow.

Both flows now follow the same picker → params pattern (G20):
- a SelectSelector picks an enum value (strategy / level / provider type)
- a follow-up step shows ONLY the params relevant to the picked enum

Centralising the schemas here means a change to (e.g.) the
``trigger_sensor_based`` form is reflected in BOTH flows automatically —
no duplication, no drift between create-flow and edit-flow.

Each schema function takes an ``initial`` dict so that defaults reflect
the current values when re-editing (otherwise the form opens with the
hardcoded defaults).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.helpers import selector

from .const import (
    AI_PROVIDER_TYPES,
    DEFAULT_CUTOFF_HOUR,
    DEFAULT_FALLBACK_HOUR,
    DEFAULT_HARD_FALLBACK_HOUR,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_MIN_SLEEP_DURATION_MINUTES,
    DEFAULT_SENSOR_BASED_DELAY_MINUTES,
    LOGICAL_DAY_FIXED_CUTOFF,
    LOGICAL_DAY_STRATEGIES,
    TRIGGER_LEVELS,
    TRIGGER_SCHEDULE,
)


# ---------------------------------------------------------------------------
# Picker schemas — one SelectSelector each, displayed as radio buttons
# ---------------------------------------------------------------------------


def logical_day_strategy_picker(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "strategy", default=initial.get("strategy", LOGICAL_DAY_FIXED_CUTOFF)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(LOGICAL_DAY_STRATEGIES),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="logical_day_strategy",
                )
            ),
        }
    )


def trigger_level_picker(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "trigger_level", default=initial.get("trigger_level", TRIGGER_SCHEDULE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(TRIGGER_LEVELS),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="trigger_level",
                )
            ),
        }
    )


def ai_provider_picker(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "ai_provider_type",
                default=initial.get("ai_provider_type", "disabled"),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(AI_PROVIDER_TYPES),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="ai_provider_type",
                )
            ),
        }
    )


# ---------------------------------------------------------------------------
# Logical-day param schemas (per strategy)
# ---------------------------------------------------------------------------


def logical_day_fixed_cutoff_params(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                "cutoff_hour", default=initial.get("cutoff_hour", DEFAULT_CUTOFF_HOUR)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


def logical_day_sleep_sensor_params(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "sleep_sensor_entity",
                default=initial.get("sleep_sensor_entity", ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(
                "awake_state", default=initial.get("awake_state", "off")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "hard_fallback_hour",
                default=initial.get("hard_fallback_hour", DEFAULT_HARD_FALLBACK_HOUR),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "lookback_hours",
                default=initial.get("lookback_hours", DEFAULT_LOOKBACK_HOURS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=72, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "min_sleep_duration_minutes",
                default=initial.get(
                    "min_sleep_duration_minutes",
                    DEFAULT_MIN_SLEEP_DURATION_MINUTES,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=600, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


# ---------------------------------------------------------------------------
# Trigger param schemas (per level)
# ---------------------------------------------------------------------------


def trigger_schedule_params(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "time", default=initial.get("time", "07:30")
            ): selector.TimeSelector(),
            vol.Optional(
                "days_of_week",
                default=initial.get(
                    "days_of_week", ["0", "1", "2", "3", "4", "5", "6"]
                ),
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
    )


def trigger_sensor_based_params(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "trigger_entity_id",
                default=initial.get("trigger_entity_id", ""),
            ): selector.EntitySelector(selector.EntitySelectorConfig()),
            vol.Required(
                "trigger_to_state", default=initial.get("trigger_to_state", "off")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "delay_minutes",
                default=initial.get(
                    "delay_minutes", DEFAULT_SENSOR_BASED_DELAY_MINUTES
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=240, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "fallback_hour",
                default=initial.get("fallback_hour", DEFAULT_FALLBACK_HOUR),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "fallback_active", default=initial.get("fallback_active", True)
            ): selector.BooleanSelector(),
        }
    )


# ---------------------------------------------------------------------------
# AI param schemas (per provider type)
# ---------------------------------------------------------------------------


def ai_ha_ai_task_params(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "entity_id", default=initial.get("entity_id", "")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="ai_task")
            ),
        }
    )


def ai_anthropic_params(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "api_key", default=initial.get("api_key", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                "model", default=initial.get("model", "claude-sonnet-4-6")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )


def ai_openai_params(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "api_key", default=initial.get("api_key", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                "model", default=initial.get("model", "gpt-4o-mini")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )
