"""Reorder fields + categories (Section 22.2 numeric-order form)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import selector


def _subentry_order_schema(entry: ConfigEntry, subentry_type: str) -> vol.Schema:
    """One numeric-order field per existing subentry of subentry_type.

    Returns an empty schema if no subentries of that type exist —
    HA still renders the form with the step description, which we use
    to tell the user there's nothing to reorder yet.
    """
    subentries = getattr(entry, "subentries", {}) or {}
    items = (
        list(subentries.values()) if isinstance(subentries, dict) else list(subentries)
    )
    fields: dict[Any, Any] = {}
    for sub in items:
        if getattr(sub, "subentry_type", None) != subentry_type:
            continue
        sid = getattr(sub, "subentry_id", None) or getattr(sub, "unique_id", None)
        if sid is None:
            continue
        data = getattr(sub, "data", {}) or {}
        current_order = int(data.get("order", 0))
        title = getattr(sub, "title", None) or data.get("label") or sid
        fields[
            vol.Optional(f"order__{sid}", default=current_order, description=str(title))
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=999, step=1, mode=selector.NumberSelectorMode.BOX
            )
        )
    return vol.Schema(fields)


def reorder_fields_schema(entry: ConfigEntry) -> vol.Schema:
    return _subentry_order_schema(entry, "field")


def reorder_categories_schema(entry: ConfigEntry) -> vol.Schema:
    return _subentry_order_schema(entry, "category")
