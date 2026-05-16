# rationale: ~340 LOC because the options flow now mirrors the
# config_flow's picker→param split for general/logical_day/trigger/AI,
# plus 4 standalone option sections. Splitting across files would
# scatter the back-to-init plumbing.
"""Options-flow handler (Section 20).

Main menu lists the 8 sections. Each section that mirrors an
initial-config-flow step (general, logical_day, trigger, AI inside
general) follows the same picker → params split — the user only sees
fields relevant to the picked enum.

Persistence model (G17):
- Sections that mirror the initial config_flow (instance_name,
  language, AI provider, logical_day, trigger) write to ``entry.data``
  via ``async_update_entry``. The runtime reads from data, so changes
  take effect immediately.
- Sections without a config_flow equivalent (notification, persistence,
  advanced, reorder_*) live under ``entry.options.<section>``.

After every save, the flow returns to the main menu (so the user can
edit several sections in one open). Selecting "Done" closes cleanly.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

from .._form_schemas import (
    ai_anthropic_params,
    ai_ha_ai_task_params,
    ai_openai_params,
    ai_provider_picker,
    logical_day_fixed_cutoff_params,
    logical_day_sleep_sensor_params,
    logical_day_strategy_picker,
    trigger_level_picker,
    trigger_schedule_params,
    trigger_sensor_based_params,
)
from ..const import (
    AI_PROVIDER_ANTHROPIC_DIRECT,
    AI_PROVIDER_DISABLED,
    AI_PROVIDER_HA_AI_TASK,
    AI_PROVIDER_OPENAI_DIRECT,
    DEFAULT_RETENTION,
    LOGICAL_DAY_FIXED_CUTOFF,
    LOGICAL_DAY_MANUAL,
    LOGICAL_DAY_SLEEP_SENSOR,
    MAX_RETENTION,
    MIN_RETENTION,
    REPORT_TYPE_MORNING,
    SUPPORTED_LANGUAGES,
    TRIGGER_EXTERNAL,
    TRIGGER_SCHEDULE,
    TRIGGER_SENSOR_BASED,
)
from .advanced import advanced_schema, current_prompt_text
from .notification import notification_schema
from .persistence import persistence_schema
from .reorder import (
    _ordered_list,
    apply_action,
    persist_order,
    reorder_form_schema,
)

_LOGGER = logging.getLogger(__name__)

_MENU_SECTIONS_ALWAYS = (
    "general_basics",
    "ai_picker",
    "trigger_picker",
    "notification",
    "persistence",
    "pool_fields",
    "pool_categories",
    "reorder_fields",
    "reorder_categories",
    "advanced",
    "view_default_prompt",
    "done",
)


class MorningBriefOptionsFlow(config_entries.OptionsFlow):
    """Multi-step options flow with picker→param splits.

    HA Core ≥ 2024.12 made ``OptionsFlow.config_entry`` a read-only
    property injected by the flow manager via ``self._config_entry`` —
    do NOT define an ``__init__`` that assigns to ``self.config_entry``
    (G16).
    """

    # ------------------------------------------------------------------ #
    # Initial values helpers
    # ------------------------------------------------------------------ #

    def _data(self) -> dict[str, Any]:
        return dict(self.config_entry.data or {})

    def _opts(self) -> dict[str, Any]:
        return dict(self.config_entry.options or {})

    def _initial_general_basics(self) -> dict[str, Any]:
        data = self._data()
        return {
            "instance_name": data.get("instance_name", ""),
            "language": data.get("language", "en"),
        }

    def _initial_ai(self) -> dict[str, Any]:
        ai: dict[str, Any] = dict(self._data().get("ai") or {})
        cfg: dict[str, Any] = dict(ai.get("config") or {})
        return {
            "ai_provider_type": ai.get("provider_type", "disabled"),
            "entity_id": cfg.get("entity_id", ""),
            "api_key": cfg.get("api_key", ""),
            "model": cfg.get("model", ""),
        }

    def _initial_logical_day(self) -> dict[str, Any]:
        ld: dict[str, Any] = dict(self._data().get("logical_day") or {})
        cfg: dict[str, Any] = dict(ld.get("config") or {})
        return {"strategy": ld.get("strategy", LOGICAL_DAY_FIXED_CUTOFF), **cfg}

    def _initial_trigger(self) -> dict[str, Any]:
        tr: dict[str, Any] = dict(self._data().get("trigger") or {})
        cfg: dict[str, Any] = dict(tr.get("config") or {})
        return {"trigger_level": tr.get("level", TRIGGER_SCHEDULE), **cfg}

    def _initial_option_section(self, section: str) -> dict[str, Any]:
        return dict(self._opts().get(section) or {})

    def _is_morning(self) -> bool:
        return self.config_entry.data.get("report_type") == REPORT_TYPE_MORNING

    # ------------------------------------------------------------------ #
    # Persistence helpers
    # ------------------------------------------------------------------ #

    def _save_to_data(self, **updates: Any) -> None:
        new_data = dict(self.config_entry.data or {})
        new_data.update(updates)
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )

    def _save_to_options(self, section: str, payload: dict[str, Any]) -> None:
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
        sections = list(_MENU_SECTIONS_ALWAYS)
        if self._is_morning():
            sections.insert(2, "logical_day_picker")
        return self.async_show_menu(step_id="init", menu_options=sections)

    # ------------------------------------------------------------------ #
    # General basics — instance_name + language only (AI moved to its own picker)
    # ------------------------------------------------------------------ #

    async def async_step_general_basics(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        import voluptuous as vol

        if user_input is not None:
            self._save_to_data(
                instance_name=user_input.get("instance_name", ""),
                language=user_input.get("language", "en"),
            )
            return await self.async_step_init()
        initial = self._initial_general_basics()
        schema = vol.Schema(
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
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="language",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="general_basics", data_schema=schema)

    # ------------------------------------------------------------------ #
    # AI picker → AI params (split per provider type)
    # ------------------------------------------------------------------ #

    async def async_step_ai_picker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            provider = user_input["ai_provider_type"]
            if provider == AI_PROVIDER_DISABLED:
                self._save_to_data(
                    ai={"provider_type": AI_PROVIDER_DISABLED, "config": {}}
                )
                return await self.async_step_init()
            if provider == AI_PROVIDER_HA_AI_TASK:
                return await self.async_step_ai_ha_ai_task()
            if provider == AI_PROVIDER_ANTHROPIC_DIRECT:
                return await self.async_step_ai_anthropic()
            if provider == AI_PROVIDER_OPENAI_DIRECT:
                return await self.async_step_ai_openai()
            return await self.async_step_init()
        return self.async_show_form(
            step_id="ai_picker",
            data_schema=ai_provider_picker(self._initial_ai()),
        )

    async def async_step_ai_ha_ai_task(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_data(
                ai={
                    "provider_type": AI_PROVIDER_HA_AI_TASK,
                    "config": dict(user_input),
                }
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="ai_ha_ai_task",
            data_schema=ai_ha_ai_task_params(self._initial_ai()),
        )

    async def async_step_ai_anthropic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_data(
                ai={
                    "provider_type": AI_PROVIDER_ANTHROPIC_DIRECT,
                    "config": dict(user_input),
                }
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="ai_anthropic",
            data_schema=ai_anthropic_params(self._initial_ai()),
        )

    async def async_step_ai_openai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_data(
                ai={
                    "provider_type": AI_PROVIDER_OPENAI_DIRECT,
                    "config": dict(user_input),
                }
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="ai_openai",
            data_schema=ai_openai_params(self._initial_ai()),
        )

    # ------------------------------------------------------------------ #
    # Logical-day picker → params (morning only)
    # ------------------------------------------------------------------ #

    async def async_step_logical_day_picker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            strategy = user_input["strategy"]
            if strategy == LOGICAL_DAY_FIXED_CUTOFF:
                return await self.async_step_logical_day_fixed_cutoff()
            if strategy == LOGICAL_DAY_SLEEP_SENSOR:
                return await self.async_step_logical_day_sleep_sensor()
            self._save_to_data(
                logical_day={"strategy": LOGICAL_DAY_MANUAL, "config": {}}
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="logical_day_picker",
            data_schema=logical_day_strategy_picker(self._initial_logical_day()),
        )

    async def async_step_logical_day_fixed_cutoff(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_data(
                logical_day={
                    "strategy": LOGICAL_DAY_FIXED_CUTOFF,
                    "config": dict(user_input),
                }
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="logical_day_fixed_cutoff",
            data_schema=logical_day_fixed_cutoff_params(self._initial_logical_day()),
        )

    async def async_step_logical_day_sleep_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_data(
                logical_day={
                    "strategy": LOGICAL_DAY_SLEEP_SENSOR,
                    "config": dict(user_input),
                }
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="logical_day_sleep_sensor",
            data_schema=logical_day_sleep_sensor_params(self._initial_logical_day()),
        )

    # ------------------------------------------------------------------ #
    # Trigger picker → params
    # ------------------------------------------------------------------ #

    async def async_step_trigger_picker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            level = user_input["trigger_level"]
            if level == TRIGGER_SCHEDULE:
                return await self.async_step_trigger_schedule()
            if level == TRIGGER_SENSOR_BASED:
                return await self.async_step_trigger_sensor_based()
            self._save_to_data(
                trigger={"level": TRIGGER_EXTERNAL, "config": {}}
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="trigger_picker",
            data_schema=trigger_level_picker(self._initial_trigger()),
        )

    async def async_step_trigger_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_data(
                trigger={
                    "level": TRIGGER_SCHEDULE,
                    "config": dict(user_input),
                }
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="trigger_schedule",
            data_schema=trigger_schedule_params(self._initial_trigger()),
        )

    async def async_step_trigger_sensor_based(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._save_to_data(
                trigger={
                    "level": TRIGGER_SENSOR_BASED,
                    "config": dict(user_input),
                }
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="trigger_sensor_based",
            data_schema=trigger_sensor_based_params(self._initial_trigger()),
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
            data_schema=notification_schema(
                self._initial_option_section("notification")
            ),
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
            data_schema=persistence_schema(
                self._initial_option_section("persistence")
            ),
        )

    # ------------------------------------------------------------------ #
    # Reorder fields / categories
    # ------------------------------------------------------------------ #

    async def async_step_reorder_fields(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._reorder_step("field", "reorder_fields", user_input)

    async def async_step_reorder_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._reorder_step(
            "category", "reorder_categories", user_input
        )

    async def _reorder_step(
        self,
        subentry_type: str,
        step_id: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Shared reorder UX (Section 22.1 — arrow up/down via SelectSelector).

        Stores the working order in ``self._reorder_state_<type>`` between
        submits so the form re-renders with the swap applied. On ``save``
        the order is persisted into each subentry via
        ``hass.config_entries.async_update_subentry``.
        """
        state_attr = f"_reorder_state_{subentry_type}"
        if not hasattr(self, state_attr) or user_input is None and not getattr(
            self, state_attr, None
        ):
            setattr(self, state_attr, _ordered_list(self.config_entry, subentry_type))
        ordered: list[tuple[str, str, int]] = getattr(self, state_attr)

        if user_input is not None:
            action = str(user_input.get("action", ""))
            if action == "__save__":
                await persist_order(
                    self.hass, self.config_entry, ordered, subentry_type
                )
                delattr(self, state_attr)
                return await self.async_step_init()
            if action == "__cancel__":
                delattr(self, state_attr)
                return await self.async_step_init()
            new_ordered = apply_action(ordered, action)
            setattr(self, state_attr, new_ordered)
            ordered = new_ordered

        if not ordered:
            # Empty state — no items to reorder. Show a form with just
            # a cancel option so the user can navigate back to the menu.
            import voluptuous as vol

            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "action", default="__cancel__"
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(
                                        value="__cancel__", label="× Retour"
                                    )
                                ],
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        )
                    }
                ),
                description_placeholders={"current_order": "_(aucun)_"},
            )

        current_order = "\n".join(
            f"{i + 1}. **{label}**" for i, (_, label, _) in enumerate(ordered)
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=reorder_form_schema(ordered),
            description_placeholders={"current_order": current_order},
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
    # View default prompt — read-only display
    # ------------------------------------------------------------------ #

    async def async_step_view_default_prompt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the default Jinja2 prompt for this instance's report_type.

        Read-only. The user can copy it into the Advanced section's
        prompt_template_override if they want to customize it.
        """
        import voluptuous as vol

        if user_input is not None:
            return await self.async_step_init()
        report_type = str(self._data().get("report_type") or REPORT_TYPE_MORNING)
        prompt = await self.hass.async_add_executor_job(
            current_prompt_text, report_type
        )
        return self.async_show_form(
            step_id="view_default_prompt",
            data_schema=vol.Schema({}),
            description_placeholders={
                "report_type": report_type,
                "prompt": prompt,
            },
        )

    # ------------------------------------------------------------------ #
    # Shared pool — Champs (CRUD on the domain-level pool of fields)
    # ------------------------------------------------------------------ #

    async def async_step_pool_fields(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._pool_menu("field", "pool_fields", user_input)

    async def async_step_pool_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._pool_menu("category", "pool_categories", user_input)

    async def _pool_menu(
        self, kind: str, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """List pool items + action SelectSelector for edit/delete."""
        import voluptuous as vol

        from ..pool import async_get_pool

        pool = async_get_pool(self.hass)
        if not pool._loaded:  # noqa: SLF001
            await pool.async_load()
        items = pool.list_fields() if kind == "field" else pool.list_categories()

        if user_input is not None:
            action = str(user_input.get("action", ""))
            if action == "__back__":
                return await self.async_step_init()
            if action.startswith("delete::"):
                item_id = action.split("::", 1)[1]
                if kind == "field":
                    await pool.async_remove_field(item_id)
                else:
                    await pool.async_remove_category(item_id)
                return await self._pool_menu(kind, step_id, None)
            if action.startswith("edit_applicable::"):
                item_id = action.split("::", 1)[1]
                self._pool_editing = {"kind": kind, "item_id": item_id}
                return await self.async_step_pool_edit_applicable()
            # Unknown action — fall through to re-render
            return await self._pool_menu(kind, step_id, None)

        # Build the action SelectSelector listing edit/delete per item
        options: list[selector.SelectOptionDict] = []
        listing_lines: list[str] = []
        for item in items:
            item_id = str(item.get("id"))
            data = item.get("data", {}) or {}
            label = (
                data.get("label") or data.get("category_id") or item_id
            )
            applicable = item.get("applicable_to") or []
            scope = (
                ", ".join(self._entry_label(eid) for eid in applicable)
                if applicable
                else "**toutes les instances**"
            )
            listing_lines.append(f"- **{label}** — visible dans : {scope}")
            options.append(
                selector.SelectOptionDict(
                    value=f"edit_applicable::{item_id}",
                    label=f"📝 Modifier visibilité — {label}",
                )
            )
            options.append(
                selector.SelectOptionDict(
                    value=f"delete::{item_id}",
                    label=f"🗑 Supprimer — {label}",
                )
            )
        options.append(
            selector.SelectOptionDict(value="__back__", label="← Retour au menu")
        )
        listing = "\n".join(listing_lines) if listing_lines else "_(pool vide)_"

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            description_placeholders={"listing": listing},
        )

    async def async_step_pool_edit_applicable(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the applicable_to list of a pool item picked from the menu."""
        import voluptuous as vol

        from ..const import DOMAIN
        from ..pool import async_get_pool

        editing = getattr(self, "_pool_editing", None) or {}
        kind = str(editing.get("kind") or "field")
        item_id = str(editing.get("item_id") or "")
        pool = async_get_pool(self.hass)
        if not pool._loaded:  # noqa: SLF001
            await pool.async_load()
        items = pool.list_fields() if kind == "field" else pool.list_categories()
        current = next((i for i in items if str(i.get("id")) == item_id), None)
        if current is None:
            # Item vanished — bounce back to the menu.
            return await self._pool_menu(
                kind,
                "pool_fields" if kind == "field" else "pool_categories",
                None,
            )

        if user_input is not None:
            applicable = list(user_input.get("applicable_to") or [])
            if kind == "field":
                await pool.async_update_field(item_id, applicable_to=applicable)
            else:
                await pool.async_update_category(
                    item_id, applicable_to=applicable
                )
            self._pool_editing = {}
            return await self._pool_menu(
                kind,
                "pool_fields" if kind == "field" else "pool_categories",
                None,
            )

        entries = list(self.hass.config_entries.async_entries(DOMAIN))
        options = [
            selector.SelectOptionDict(
                value=e.entry_id, label=e.title or e.entry_id
            )
            for e in entries
        ]
        return self.async_show_form(
            step_id="pool_edit_applicable",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "applicable_to",
                        default=list(current.get("applicable_to") or []),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            description_placeholders={
                "label": str(
                    current.get("data", {}).get("label") or item_id
                ),
                "kind": "champ" if kind == "field" else "catégorie",
            },
        )

    def _entry_label(self, entry_id: str) -> str:
        """Human-readable label for an entry_id, used in pool listings."""
        from ..const import DOMAIN

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return entry_id
        return entry.title or entry.data.get("instance_name") or entry_id

    # ------------------------------------------------------------------ #
    # Done — close the dialog
    # ------------------------------------------------------------------ #

    async def async_step_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(
            title="", data=dict(self.config_entry.options or {})
        )


__all__ = ["MorningBriefOptionsFlow"]
