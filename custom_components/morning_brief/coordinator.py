"""DataUpdateCoordinator for the morning_brief integration.

Phase 1 skeleton. The coordinator owns the per-instance runtime state
(BriefStore handle, logical-day strategy, trigger registration, report builder).
Real `_async_update_data` and trigger wiring land in Phases 7 + 9.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .store import BriefStore

_LOGGER = logging.getLogger(__name__)


class MorningBriefCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator that holds the latest brief for one instance.

    Refresh is event-driven (triggered by user-configured schedule / sensor /
    external service call — see Section 16), not polled. We therefore do NOT
    set `update_interval`; updates happen only when something calls
    `async_request_refresh()` or `async_refresh()`.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        store: BriefStore,
    ) -> None:
        """Initialise the coordinator for one config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=None,
        )
        self.entry = entry
        self.store = store

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Produce the next brief.

        Phase 1: returns the last stored brief, if any. The real generation
        pipeline (provider fan-out → comparisons → anomaly → AI → canonical
        JSON → render → persist) lands in Phase 7 (`reports/`) and is wired
        here in Phase 9.
        """
        latest = await self.store.get_latest()
        if latest is None:
            return None
        return latest.get("canonical_json")
