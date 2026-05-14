"""The morning_brief integration.

Entry point for Home Assistant. Phase 1 wires only the coordinator and the
per-instance BriefStore; platform setup (sensor/button), services and triggers
are wired in Phases 7–9.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DEFAULT_RETENTION, DOMAIN
from .coordinator import MorningBriefCoordinator
from .store import BriefStore

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a morning_brief instance from its config entry.

    Per R10, this returns quickly: heavy lifting happens lazily on first
    coordinator refresh (Phase 7+).
    """
    retention = entry.options.get("retention", DEFAULT_RETENTION)
    store = BriefStore(hass, entry.entry_id, retention=retention)
    coordinator = MorningBriefCoordinator(hass, entry, store)

    # First refresh just reads the latest persisted brief, if any.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry. Drops in-memory state; storage is untouched."""
    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove an instance: also delete its persisted storage file."""
    store = BriefStore(hass, entry.entry_id)
    try:
        await store.async_remove()
    except Exception:  # noqa: BLE001 — entry-point fallback per R6
        _LOGGER.exception("Failed to remove storage for entry %s", entry.entry_id)
