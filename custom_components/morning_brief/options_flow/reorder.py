"""Reorder fields + categories (Section 22.1 spec: arrow up/down UX).

The options flow renders a SelectSelector listing actions:
- ``↑ <Label>`` for each item that can move up
- ``↓ <Label>`` for each item that can move down
- ``💾 Sauvegarder l'ordre`` to persist
- ``× Annuler`` to discard

Each submit re-renders the form with the updated order. The form is
also accompanied by a description block showing the current order so
the user can see what's happening between clicks.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import selector

from ..subentries import iter_subentries

_LOGGER = logging.getLogger(__name__)


def _ordered_list(entry: ConfigEntry, subentry_type: str) -> list[tuple[str, str, int]]:
    """Return (sid, label, order) tuples sorted by current order."""
    items: list[tuple[str, str, int]] = []
    for sub in iter_subentries(entry):
        if getattr(sub, "subentry_type", None) != subentry_type:
            continue
        sid = getattr(sub, "subentry_id", None) or getattr(sub, "unique_id", None)
        if sid is None:
            continue
        data = getattr(sub, "data", {}) or {}
        label = (
            data.get("label") or getattr(sub, "title", None) or str(sid)
        )
        order = int(data.get("order", 0))
        items.append((str(sid), str(label), order))
    items.sort(key=lambda t: t[2])
    return items


def build_action_options(
    ordered: list[tuple[str, str, int]]
) -> list[selector.SelectOptionDict]:
    """Build the SelectSelector options for the current ordered list."""
    out: list[selector.SelectOptionDict] = []
    n = len(ordered)
    for i, (sid, label, _order) in enumerate(ordered):
        if i > 0:
            out.append(
                selector.SelectOptionDict(value=f"up::{sid}", label=f"↑ {label}")
            )
        if i < n - 1:
            out.append(
                selector.SelectOptionDict(
                    value=f"down::{sid}", label=f"↓ {label}"
                )
            )
    out.append(selector.SelectOptionDict(value="__save__", label="💾 Sauvegarder l'ordre"))
    out.append(selector.SelectOptionDict(value="__cancel__", label="× Annuler"))
    return out


def reorder_form_schema(
    ordered: list[tuple[str, str, int]],
) -> vol.Schema:
    """Schema with one SelectSelector listing all reorder actions."""
    return vol.Schema(
        {
            vol.Required("action"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=build_action_options(ordered),
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
    )


def apply_action(
    ordered: list[tuple[str, str, int]], action: str
) -> list[tuple[str, str, int]]:
    """Apply ``up::sid`` or ``down::sid`` and return a NEW list (no mutation)."""
    if "::" not in action:
        return ordered
    direction, sid = action.split("::", 1)
    new_list = list(ordered)
    for i, (this_sid, _, _) in enumerate(new_list):
        if this_sid != sid:
            continue
        if direction == "up" and i > 0:
            new_list[i - 1], new_list[i] = new_list[i], new_list[i - 1]
        elif direction == "down" and i < len(new_list) - 1:
            new_list[i], new_list[i + 1] = new_list[i + 1], new_list[i]
        break
    return new_list


async def persist_order(
    hass: Any, entry: ConfigEntry, ordered: list[tuple[str, str, int]],
    subentry_type: str,
) -> None:
    """Write the new order back to each matching subentry."""
    update_subentry = getattr(hass.config_entries, "async_update_subentry", None)
    if update_subentry is None:
        _LOGGER.warning(
            "reorder: HA does not expose async_update_subentry; nothing persisted"
        )
        return
    sub_by_id = {
        getattr(s, "subentry_id", None) or getattr(s, "unique_id", None): s
        for s in iter_subentries(entry)
    }
    for new_order, (sid, _label, _old_order) in enumerate(ordered):
        sub = sub_by_id.get(sid)
        if sub is None or getattr(sub, "subentry_type", None) != subentry_type:
            continue
        new_data = dict(getattr(sub, "data", {}) or {})
        new_data["order"] = new_order * 10  # leave room (10, 20, 30…)
        try:
            update_subentry(entry, sub, data=new_data)
        except Exception:  # noqa: BLE001 — log + continue, don't crash the flow
            _LOGGER.exception(
                "reorder: failed to update subentry %s (type=%s)", sid, subentry_type
            )
