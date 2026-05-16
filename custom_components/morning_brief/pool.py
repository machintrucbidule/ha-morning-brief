# rationale: ~260 LOC because the pool wraps a domain-level Store with
# 6 CRUD methods (add/update/remove × fields/categories) plus the
# applicability filter and the one-shot migration from per-instance
# subentries. Keeping it in one module avoids scattering the store
# schema, the lock, and the migration logic across files.
"""Shared pool of fields & categories across all morning_brief instances.

DECISIONS.md (2026-05-16): the original D12 model — fields and
categories defined per-instance as HA subentries — is unusable in
practice because creating a morning + evening + weekly setup means
duplicating every field three times. This module replaces it with a
single domain-level store where each field / category carries an
``applicable_to: list[entry_id]`` so the same item appears in several
instances' briefs without being duplicated.

Pool storage layout
-------------------
``hass.data[DOMAIN]["pool"]`` is the in-memory cache of the latest
loaded state. The on-disk store key is ``morning_brief_pool`` (version
1).

```
{
    "fields": {
        "<uuid>": {
            "data": {...field config...},
            "applicable_to": ["<entry_id_morning>", "<entry_id_weekly>"],
            "created_at": "ISO-8601",
            "updated_at": "ISO-8601"
        },
        ...
    },
    "categories": {
        "<uuid>": {
            "data": {...category config...},
            "applicable_to": [],  # empty = visible in all instances
            "created_at": "...",
            "updated_at": "..."
        },
        ...
    }
}
```

``applicable_to == []`` means "visible in every morning_brief
instance" — the default for items that aren't explicitly scoped.
"""

from __future__ import annotations

import asyncio
import logging
import uuid as uuid_module
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

POOL_STORAGE_KEY = "morning_brief_pool"
POOL_STORAGE_VERSION = 1

_PoolDict = dict[str, dict[str, dict[str, Any]]]


def _empty_pool() -> _PoolDict:
    return {"fields": {}, "categories": {}}


class FieldsCategoriesPool:
    """Domain-level shared pool for fields and categories.

    One instance per HA process — stored on ``hass.data[DOMAIN]["pool"]``
    after the first ``async_get(hass)`` call. Thread-safe writes via a
    single asyncio lock.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[_PoolDict] = Store(
            hass, POOL_STORAGE_VERSION, POOL_STORAGE_KEY
        )
        self._lock = asyncio.Lock()
        self._cache: _PoolDict = _empty_pool()
        self._loaded = False

    # ---------------------------------------------------------------- #
    # Loading
    # ---------------------------------------------------------------- #

    async def async_load(self) -> None:
        """Hydrate the in-memory cache from disk (call once at setup)."""
        async with self._lock:
            data = await self._store.async_load()
            if data is None:
                self._cache = _empty_pool()
            else:
                self._cache = {
                    "fields": dict(data.get("fields", {}) or {}),
                    "categories": dict(data.get("categories", {}) or {}),
                }
            self._loaded = True

    async def _async_save_locked(self) -> None:
        """Persist the cache. Must be called while holding ``_lock``."""
        await self._store.async_save(self._cache)

    # ---------------------------------------------------------------- #
    # Read API — synchronous (operates on the in-memory cache)
    # ---------------------------------------------------------------- #

    def list_fields(self) -> list[dict[str, Any]]:
        """All fields in the pool, each as a flat dict (data + meta)."""
        return [
            {**v, "id": k} for k, v in self._cache.get("fields", {}).items()
        ]

    def list_categories(self) -> list[dict[str, Any]]:
        """All categories in the pool, each as a flat dict (data + meta)."""
        return [
            {**v, "id": k} for k, v in self._cache.get("categories", {}).items()
        ]

    def fields_for_entry(self, entry_id: str) -> list[dict[str, Any]]:
        """Filter the pool to fields visible in ``entry_id``."""
        return [
            f
            for f in self.list_fields()
            if not f.get("applicable_to") or entry_id in f["applicable_to"]
        ]

    def categories_for_entry(self, entry_id: str) -> list[dict[str, Any]]:
        """Filter the pool to categories visible in ``entry_id``."""
        return [
            c
            for c in self.list_categories()
            if not c.get("applicable_to") or entry_id in c["applicable_to"]
        ]

    # ---------------------------------------------------------------- #
    # Write API — async (acquires lock, persists)
    # ---------------------------------------------------------------- #

    async def async_add_field(
        self, data: dict[str, Any], applicable_to: list[str] | None = None
    ) -> str:
        return await self._async_add("fields", data, applicable_to or [])

    async def async_add_category(
        self, data: dict[str, Any], applicable_to: list[str] | None = None
    ) -> str:
        return await self._async_add("categories", data, applicable_to or [])

    async def async_update_field(
        self,
        item_id: str,
        data: dict[str, Any] | None = None,
        applicable_to: list[str] | None = None,
    ) -> None:
        await self._async_update("fields", item_id, data, applicable_to)

    async def async_update_category(
        self,
        item_id: str,
        data: dict[str, Any] | None = None,
        applicable_to: list[str] | None = None,
    ) -> None:
        await self._async_update("categories", item_id, data, applicable_to)

    async def async_remove_field(self, item_id: str) -> bool:
        return await self._async_remove("fields", item_id)

    async def async_remove_category(self, item_id: str) -> bool:
        return await self._async_remove("categories", item_id)

    # ---------------------------------------------------------------- #
    # Internal helpers
    # ---------------------------------------------------------------- #

    async def _async_add(
        self, bucket: str, data: dict[str, Any], applicable_to: list[str]
    ) -> str:
        async with self._lock:
            item_id = str(uuid_module.uuid4())
            now = dt_util.utcnow().isoformat()
            self._cache.setdefault(bucket, {})[item_id] = {
                "data": dict(data),
                "applicable_to": list(applicable_to),
                "created_at": now,
                "updated_at": now,
            }
            await self._async_save_locked()
            return item_id

    async def _async_update(
        self,
        bucket: str,
        item_id: str,
        data: dict[str, Any] | None,
        applicable_to: list[str] | None,
    ) -> None:
        async with self._lock:
            existing = self._cache.get(bucket, {}).get(item_id)
            if existing is None:
                _LOGGER.warning(
                    "pool: cannot update %s/%s (not found)", bucket, item_id
                )
                return
            if data is not None:
                existing["data"] = dict(data)
            if applicable_to is not None:
                existing["applicable_to"] = list(applicable_to)
            existing["updated_at"] = dt_util.utcnow().isoformat()
            await self._async_save_locked()

    async def _async_remove(self, bucket: str, item_id: str) -> bool:
        async with self._lock:
            if item_id not in self._cache.get(bucket, {}):
                return False
            del self._cache[bucket][item_id]
            await self._async_save_locked()
            return True

    # ---------------------------------------------------------------- #
    # One-shot migration from per-instance subentries
    # ---------------------------------------------------------------- #

    async def async_migrate_from_subentries(self) -> int:
        """Aggregate every existing subentry of every morning_brief entry
        into the pool.

        Returns the number of items migrated. Safe to call multiple
        times — dedupes via the migrated_subentry_id stored in each
        pool item's data. We never delete the source subentries —
        rollback to rc.8 stays possible.
        """
        from .subentries import iter_subentries

        if not self._loaded:
            await self.async_load()
        entries = self._hass.config_entries.async_entries(DOMAIN)
        # Build a fast lookup of already-migrated subentry ids
        async with self._lock:
            already: set[str] = set()
            for bucket in ("fields", "categories"):
                for item in self._cache.get(bucket, {}).values():
                    src_id = item.get("data", {}).get("_migrated_subentry_id")
                    if src_id:
                        already.add(str(src_id))
        migrated = 0
        for entry in entries:
            for sub in iter_subentries(entry):
                sid = getattr(sub, "subentry_id", None) or getattr(
                    sub, "unique_id", None
                )
                if not sid or str(sid) in already:
                    continue
                sub_type = getattr(sub, "subentry_type", None) or ""
                if sub_type not in ("field", "category"):
                    continue
                data = dict(getattr(sub, "data", {}) or {})
                data["_migrated_subentry_id"] = str(sid)
                if sub_type == "field":
                    await self.async_add_field(
                        data, applicable_to=[entry.entry_id]
                    )
                else:
                    await self.async_add_category(
                        data, applicable_to=[entry.entry_id]
                    )
                migrated += 1
        if migrated:
            _LOGGER.info("pool: migrated %d subentries into the pool", migrated)
        return migrated


def async_get_pool(hass: HomeAssistant) -> FieldsCategoriesPool:
    """Return the shared pool (creates it on first call)."""
    pool = hass.data.setdefault(DOMAIN, {}).get("pool")
    if pool is None:
        pool = FieldsCategoriesPool(hass)
        hass.data[DOMAIN]["pool"] = pool
    return cast(FieldsCategoriesPool, pool)
