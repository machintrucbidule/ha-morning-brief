"""Tests for the BriefStore (Section 17.4)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.const import (
    DEFAULT_RETENTION,
    MAX_RETENTION,
    MIN_RETENTION,
)
from custom_components.morning_brief.store import BriefStore


def _make_brief(uuid: str, logical_date: str = "2026-05-14") -> dict[str, Any]:
    """Build a minimal brief dict for store tests."""
    return {
        "uuid": uuid,
        "generated_at": f"{logical_date}T07:00:00+02:00",
        "report_type": "morning",
        "logical_date": logical_date,
        "canonical_json": {"schema_version": 1, "meta": {"instance_id": uuid}},
        "rendered_markdown": "",
        "notification_short": "",
    }


async def test_add_and_get_latest(hass: HomeAssistant) -> None:
    """Adding a brief makes it retrievable as latest and by UUID."""
    store = BriefStore(hass, "entry-1", retention=5)
    await store.add_brief(_make_brief("a"))

    latest = await store.get_latest()
    assert latest is not None
    assert latest["uuid"] == "a"

    by_uuid = await store.get_brief("a")
    assert by_uuid is not None
    assert by_uuid["uuid"] == "a"


async def test_newest_first_ordering(hass: HomeAssistant) -> None:
    """The store keeps the newest brief at index 0 (LIFO insertion order)."""
    store = BriefStore(hass, "entry-2", retention=5)
    for uuid in ("a", "b", "c"):
        await store.add_brief(_make_brief(uuid))

    briefs = await store.list_briefs()
    assert [b["uuid"] for b in briefs] == ["c", "b", "a"]


async def test_fifo_rotation_at_retention_limit(hass: HomeAssistant) -> None:
    """Beyond `retention`, the oldest briefs are dropped.

    Uses retention=5 (MIN_RETENTION); the spec D16 forbids retention < 5.
    """
    store = BriefStore(hass, "entry-3", retention=5)
    for uuid in ("a", "b", "c", "d", "e", "f", "g"):
        await store.add_brief(_make_brief(uuid))

    briefs = await store.list_briefs()
    assert len(briefs) == 5
    # Newest first; oldest two ("a" and "b") were rotated out.
    assert [b["uuid"] for b in briefs] == ["g", "f", "e", "d", "c"]
    assert await store.get_brief("a") is None
    assert await store.get_brief("b") is None


async def test_get_brief_returns_none_when_missing(hass: HomeAssistant) -> None:
    """Unknown UUIDs return None, not an exception."""
    store = BriefStore(hass, "entry-4", retention=5)
    await store.add_brief(_make_brief("a"))
    assert await store.get_brief("zzz") is None


async def test_get_latest_empty_store(hass: HomeAssistant) -> None:
    """An empty store yields None for get_latest and [] for list_briefs."""
    store = BriefStore(hass, "entry-5", retention=5)
    assert await store.get_latest() is None
    assert await store.list_briefs() == []


async def test_clear(hass: HomeAssistant) -> None:
    """Clear removes every brief but preserves the underlying file."""
    store = BriefStore(hass, "entry-6", retention=5)
    for uuid in ("a", "b"):
        await store.add_brief(_make_brief(uuid))
    await store.clear()
    assert await store.list_briefs() == []
    assert await store.get_latest() is None


async def test_retention_is_clamped(hass: HomeAssistant) -> None:
    """Retention is clamped into [MIN_RETENTION, MAX_RETENTION]."""
    too_low = BriefStore(hass, "entry-7", retention=1)
    assert too_low.retention == MIN_RETENTION

    too_high = BriefStore(hass, "entry-8", retention=10_000)
    assert too_high.retention == MAX_RETENTION

    default = BriefStore(hass, "entry-9")
    assert default.retention == DEFAULT_RETENTION


async def test_set_retention_updates_cap_on_next_add(hass: HomeAssistant) -> None:
    """Shrinking retention via set_retention takes effect on the next add.

    Spec D16 forbids retention < MIN_RETENTION (5), so we shrink from 10 to 5
    and verify the next add evicts down to 5 briefs.
    """
    store = BriefStore(hass, "entry-10", retention=10)
    for uuid in ("a", "b", "c", "d", "e", "f", "g"):
        await store.add_brief(_make_brief(uuid))
    assert len(await store.list_briefs()) == 7

    store.set_retention(MIN_RETENTION)
    await store.add_brief(_make_brief("h"))
    briefs = await store.list_briefs()
    assert len(briefs) == MIN_RETENTION
    assert [b["uuid"] for b in briefs] == ["h", "g", "f", "e", "d"]


async def test_async_remove_drops_storage(hass: HomeAssistant) -> None:
    """async_remove deletes the storage; a fresh store after returns []."""
    store = BriefStore(hass, "entry-11", retention=5)
    await store.add_brief(_make_brief("a"))
    await store.async_remove()

    fresh = BriefStore(hass, "entry-11", retention=5)
    assert await fresh.list_briefs() == []
