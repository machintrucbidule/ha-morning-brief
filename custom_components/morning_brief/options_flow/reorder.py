"""Reorder fields + categories (Section 22.2 numeric-order form)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry


def _subentry_order_schema(entry: ConfigEntry, subentry_type: str) -> vol.Schema:
    """One order int field per existing subentry of subentry_type."""
    subentries = getattr(entry, "subentries", {}) or {}
    items = (
        list(subentries.values()) if isinstance(subentries, dict) else list(subentries)
    )
    fields: dict = {}
    for sub in items:
        if getattr(sub, "subentry_type", None) != subentry_type:
            continue
        sid = getattr(sub, "subentry_id", None) or getattr(sub, "unique_id", None)
        if sid is None:
            continue
        data = getattr(sub, "data", {}) or {}
        current_order = int(data.get("order", 0))
        fields[vol.Optional(f"order__{sid}", default=current_order)] = vol.All(
            int, vol.Range(min=0)
        )
    return vol.Schema(fields)


def reorder_fields_schema(entry: ConfigEntry) -> vol.Schema:
    return _subentry_order_schema(entry, "field")


def reorder_categories_schema(entry: ConfigEntry) -> vol.Schema:
    return _subentry_order_schema(entry, "category")
