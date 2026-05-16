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

    # Shared pool of fields & categories (D12 override per DECISIONS.md).
    # Load once per HA process; subsequent entries hit the cache.
    from .pool import async_get_pool

    pool = async_get_pool(hass)
    if not pool._loaded:  # noqa: SLF001 — one-shot bootstrap
        await pool.async_load()
        # One-shot migration: any pre-rc.9 per-instance subentry that
        # isn't already in the pool gets copied over (idempotent — the
        # migrated_subentry_id flag prevents duplicates on restart).
        await pool.async_migrate_from_subentries()

    _attach_logical_day_strategy(hass, entry, coordinator)
    _attach_ai_provider(hass, entry, coordinator)
    await _attach_prompt_template(hass, coordinator)
    _attach_pool_view(entry, coordinator, pool)
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


def _attach_pool_view(
    entry: ConfigEntry,
    coordinator: MorningBriefCoordinator,
    pool: Any,  # FieldsCategoriesPool — typed as Any to avoid import cycle
) -> None:
    """Read fields + categories applicable to this entry from the pool.

    Replaces the old per-entry subentries reader (D12 override). Each
    pool item's ``applicable_to`` list is filtered against this entry's
    ``entry_id``; items with an empty applicable_to are visible in
    every instance.
    """
    fields: list[dict[str, Any]] = []
    for item in pool.fields_for_entry(entry.entry_id):
        fields.append(dict(item.get("data", {}) or {}))
    categories: list[dict[str, Any]] = []
    for item in pool.categories_for_entry(entry.entry_id):
        data = dict(item.get("data", {}) or {})
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


async def _maybe_copy_subentries(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """One-shot copy of subentries from a source instance (Section 19 step 6).

    Verbose INFO logs at every step so the user can diagnose via the
    HA logs (Settings → Logs, filter on morning_brief) why a copy was
    skipped on their HA version.
    """
    from .subentries import iter_subentries

    source_id = entry.data.get("copy_from_instance")
    if not source_id or entry.data.get("_copy_done"):
        return
    _LOGGER.info(
        "copy_from: starting copy from %s into %s",
        source_id,
        entry.entry_id,
    )
    source = hass.config_entries.async_get_entry(str(source_id))
    new_data: dict[str, Any] = dict(entry.data)
    new_data["_copy_done"] = True
    if source is None:
        _LOGGER.warning(
            "copy_from: source instance %s not found — skipping (marking _copy_done)",
            source_id,
        )
        hass.config_entries.async_update_entry(entry, data=new_data)
        return
    source_subs = list(iter_subentries(source))
    _LOGGER.info(
        "copy_from: source %s exposes %d subentries",
        source_id,
        len(source_subs),
    )
    add_subentry = getattr(hass.config_entries, "async_add_subentry", None)
    if add_subentry is None:
        _LOGGER.warning(
            "copy_from: HA does not expose async_add_subentry — skipping"
        )
        hass.config_entries.async_update_entry(entry, data=new_data)
        return
    # Resolve the subentry container class HA expects. Tried in order:
    # 1. ConfigSubentry (the actual config object on HA ≥ 2025.x)
    # 2. ConfigSubentryData (a TypedDict alias on some versions)
    # 3. dict (last resort — HA may coerce internally)
    sub_cls: Any = None
    for name in ("ConfigSubentry", "ConfigSubentryData"):
        try:
            sub_cls = getattr(
                __import__(
                    "homeassistant.config_entries", fromlist=[name]
                ),
                name,
            )
            _LOGGER.info("copy_from: using %s as subentry container", name)
            break
        except (ImportError, AttributeError):
            continue
    copied = 0
    for sub in source_subs:
        try:
            sub_type = getattr(sub, "subentry_type", None) or ""
            if sub_type not in ("field", "category"):
                _LOGGER.debug(
                    "copy_from: skipping subentry of unsupported type %s",
                    sub_type,
                )
                continue
            sub_data = dict(getattr(sub, "data", {}) or {})
            sub_title = str(getattr(sub, "title", "") or "")
            if sub_cls is None:
                payload: Any = {
                    "data": sub_data,
                    "subentry_type": sub_type,
                    "title": sub_title,
                    "unique_id": None,
                }
            else:
                payload = sub_cls(
                    data=sub_data,
                    subentry_type=sub_type,
                    title=sub_title,
                    unique_id=None,
                )
            add_subentry(entry, payload)
            copied += 1
            _LOGGER.info(
                "copy_from: copied %s subentry %r",
                sub_type,
                sub_title,
            )
        except Exception:  # noqa: BLE001 — entry-point guard
            _LOGGER.exception(
                "copy_from: failed to copy subentry %s from %s",
                getattr(sub, "subentry_id", "?"),
                source_id,
            )
    _LOGGER.info(
        "copy_from: copied %d subentries from %s into %s",
        copied,
        source_id,
        entry.entry_id,
    )
    hass.config_entries.async_update_entry(entry, data=new_data)


def _attach_options(
    entry: ConfigEntry, coordinator: MorningBriefCoordinator
) -> None:
    """Pull language + advanced.user_custom_context out of entry.options/data."""
    opts: dict[str, Any] = dict(entry.options or {})
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
