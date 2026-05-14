"""Per-instance brief storage with FIFO rotation.

Uses HA's `Store` helper (see Section 17.3 of the spec). One JSON file per
config entry, stored under `.storage/morning_brief_<entry_id>`. Newest brief
first; oldest dropped when the retention cap is exceeded.

Last-write-wins for concurrent writes is acceptable (D16).
"""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_RETENTION,
    MAX_RETENTION,
    MIN_RETENTION,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .exceptions import StoreError

_LOGGER = logging.getLogger(__name__)


def _clamp_retention(retention: int) -> int:
    """Force retention into the allowed [MIN_RETENTION, MAX_RETENTION] range."""
    if retention < MIN_RETENTION:
        return MIN_RETENTION
    if retention > MAX_RETENTION:
        return MAX_RETENTION
    return retention


class BriefStore:
    """Wraps `homeassistant.helpers.storage.Store` with FIFO rotation.

    Schema (Section 17.2): ``{"briefs": [<brief>, <brief>, ...]}`` — newest
    first. Each brief is the dict described in :class:`types.StoredBrief`.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        retention: int = DEFAULT_RETENTION,
    ) -> None:
        """Build a store for one config entry.

        Args:
            hass: the Home Assistant instance.
            entry_id: config entry identifier — used to namespace the storage key.
            retention: maximum number of briefs to keep. Clamped to
                ``[MIN_RETENTION, MAX_RETENTION]``.
        """
        self._hass = hass
        self._entry_id = entry_id
        self._retention = _clamp_retention(retention)
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=STORAGE_VERSION,
            key=f"{STORAGE_KEY_PREFIX}_{entry_id}",
        )

    @property
    def retention(self) -> int:
        """Current retention cap (already clamped)."""
        return self._retention

    def set_retention(self, retention: int) -> None:
        """Update the retention cap. Does not rewrite existing data."""
        self._retention = _clamp_retention(retention)

    async def _load(self) -> dict[str, Any]:
        """Load raw store data, defaulting to an empty `{"briefs": []}`."""
        try:
            data = await self._store.async_load()
        except (OSError, ValueError) as err:
            _LOGGER.exception("BriefStore load failed for %s", self._entry_id)
            raise StoreError(str(err)) from err
        if data is None:
            return {"briefs": []}
        if "briefs" not in data or not isinstance(data["briefs"], list):
            data["briefs"] = []
        return data

    async def add_brief(self, brief: dict[str, Any]) -> None:
        """Insert a brief at the head, then truncate to ``retention``.

        FIFO semantics: newest first, oldest dropped beyond ``retention``.
        """
        data = await self._load()
        briefs = cast(list[dict[str, Any]], data["briefs"])
        briefs.insert(0, brief)
        if len(briefs) > self._retention:
            del briefs[self._retention :]
        data["briefs"] = briefs
        try:
            await self._store.async_save(data)
        except (OSError, ValueError) as err:
            _LOGGER.exception("BriefStore save failed for %s", self._entry_id)
            raise StoreError(str(err)) from err

    async def list_briefs(self) -> list[dict[str, Any]]:
        """Return all stored briefs, newest first."""
        data = await self._load()
        return cast(list[dict[str, Any]], data["briefs"])

    async def get_brief(self, uuid: str) -> dict[str, Any] | None:
        """Return the stored brief with the given UUID, or ``None``."""
        for brief in await self.list_briefs():
            if brief.get("uuid") == uuid:
                return brief
        return None

    async def get_latest(self) -> dict[str, Any] | None:
        """Return the most recent brief, or ``None`` if the store is empty."""
        briefs = await self.list_briefs()
        return briefs[0] if briefs else None

    async def clear(self) -> None:
        """Remove every brief from the store."""
        try:
            await self._store.async_save({"briefs": []})
        except (OSError, ValueError) as err:
            _LOGGER.exception("BriefStore clear failed for %s", self._entry_id)
            raise StoreError(str(err)) from err

    async def async_remove(self) -> None:
        """Delete the underlying storage file (on instance removal)."""
        try:
            await self._store.async_remove()
        except (OSError, ValueError) as err:
            _LOGGER.exception("BriefStore remove failed for %s", self._entry_id)
            raise StoreError(str(err)) from err
