"""The morning_brief integration.

Entry point for Home Assistant. Phase 9 wires the full integration:
- builds the AI provider / logical-day strategy / prompt template
- populates the coordinator with field/category subentries
- forwards setup to the sensor + button platforms
- registers the morning_brief.* services
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .ai import create_ai_provider
from .ai.prompt_template import PromptTemplate
from .const import (
    AI_PROVIDER_DISABLED,
    DEFAULT_LANGUAGE,
    DEFAULT_RETENTION,
    DOMAIN,
    LOGICAL_DAY_FIXED_CUTOFF,
)
from .coordinator import MorningBriefCoordinator
from .logical_day import create_strategy
from .services import async_register_services, async_unregister_services
from .store import BriefStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a morning_brief instance from its config entry.

    Returns quickly (R10): expensive work (AI provider validation, sensor
    fan-out) happens on the first coordinator refresh.
    """
    retention = int(entry.options.get("persistence", {}).get("retention", DEFAULT_RETENTION))
    store = BriefStore(hass, entry.entry_id, retention=retention)
    coordinator = MorningBriefCoordinator(hass, entry, store)

    _attach_logical_day_strategy(hass, entry, coordinator)
    _attach_ai_provider(hass, entry, coordinator)
    await _attach_prompt_template(hass, coordinator)
    _attach_subentries(entry, coordinator)
    _attach_options(entry, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Initial refresh reads the latest persisted brief — does NOT regenerate.
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry. Drops in-memory state; storage is untouched."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop(entry.entry_id, None)
        async_unregister_services(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove an instance: also delete its persisted storage file."""
    store = BriefStore(hass, entry.entry_id)
    try:
        await store.async_remove()
    except Exception:  # noqa: BLE001 — entry-point fallback per R6
        _LOGGER.exception("Failed to remove storage for entry %s", entry.entry_id)


# --------------------------------------------------------------------------- #
# Setup helpers — keep async_setup_entry tight.
# --------------------------------------------------------------------------- #


def _attach_logical_day_strategy(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: MorningBriefCoordinator
) -> None:
    """Build the configured logical-day strategy, falling back to fixed_cutoff."""
    cfg = entry.data.get("logical_day") or {}
    strategy_type = str(cfg.get("strategy", LOGICAL_DAY_FIXED_CUTOFF))
    try:
        coordinator.logical_day_strategy = create_strategy(
            hass, strategy_type, dict(cfg.get("config") or {})
        )
    except Exception:  # noqa: BLE001 — fall back to the safest default
        _LOGGER.warning(
            "Logical-day strategy %s failed validation — using fixed_cutoff default",
            strategy_type,
        )
        coordinator.logical_day_strategy = create_strategy(
            hass, LOGICAL_DAY_FIXED_CUTOFF, {}
        )


def _attach_ai_provider(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: MorningBriefCoordinator
) -> None:
    """Build the configured AI provider, falling back to disabled."""
    cfg = entry.data.get("ai") or {}
    provider_type = str(cfg.get("provider_type", AI_PROVIDER_DISABLED))
    try:
        coordinator.ai_provider = create_ai_provider(
            hass, provider_type, dict(cfg.get("config") or {})
        )
    except Exception:  # noqa: BLE001 — fall back to disabled (D9)
        _LOGGER.warning(
            "AI provider %s failed validation — using disabled fallback",
            provider_type,
        )
        coordinator.ai_provider = create_ai_provider(hass, AI_PROVIDER_DISABLED, {})


async def _attach_prompt_template(
    hass: HomeAssistant, coordinator: MorningBriefCoordinator
) -> None:
    """Pre-load the per-report-type prompt template (async — uses executor)."""
    try:
        coordinator.prompt_template = await PromptTemplate.for_report_type(
            hass, coordinator.report_type
        )
    except Exception:  # noqa: BLE001
        _LOGGER.warning(
            "Prompt template %s_v1.txt failed to load — proceeding without",
            coordinator.report_type,
        )
        coordinator.prompt_template = None


def _attach_subentries(
    entry: ConfigEntry, coordinator: MorningBriefCoordinator
) -> None:
    """Split the entry's subentries into fields + categories lists."""
    subentries = getattr(entry, "subentries", {}) or {}
    items: list[Any] = (
        list(subentries.values()) if isinstance(subentries, dict) else list(subentries)
    )
    fields: list[dict[str, Any]] = []
    categories: list[dict[str, Any]] = []
    for sub in items:
        kind = getattr(sub, "subentry_type", None) or getattr(sub, "type", None)
        data = dict(getattr(sub, "data", {}) or {})
        if kind == "field":
            fields.append(data)
        elif kind == "category":
            categories.append(
                {
                    "id": data.get("category_id") or data.get("id"),
                    "label": data.get("label", ""),
                    "icon": data.get("icon", ""),
                    "order": int(data.get("order", 0)),
                    "display_when_empty": bool(data.get("display_when_empty", False)),
                }
            )
    coordinator.fields = fields
    coordinator.categories = categories


def _attach_options(
    entry: ConfigEntry, coordinator: MorningBriefCoordinator
) -> None:
    """Pull language + advanced.user_custom_context out of entry.options/data."""
    opts = entry.options or {}
    general = opts.get("general", {}) or {}
    advanced = opts.get("advanced", {}) or {}
    coordinator.language = str(
        general.get("language") or entry.data.get("language") or DEFAULT_LANGUAGE
    )
    coordinator.instance_name = str(
        general.get("instance_name") or entry.data.get("instance_name") or entry.title
    )
    coordinator.user_custom_context = (
        advanced.get("user_custom_context") or None
    )
