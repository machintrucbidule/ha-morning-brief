"""Subentry registry (D3, Section 21).

Two subentry types: `field` (sensor + display + comparisons + anomaly
config) and `category` (display grouping). Each has its own
SubentryFlowHandler exposed via the integration's manifest
``supported_subentry_types`` list.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .category.flow import CategorySubentryFlow
from .field.flow import FieldSubentryFlow

SUBENTRY_FLOWS = {
    "field": FieldSubentryFlow,
    "category": CategorySubentryFlow,
}


def iter_subentries(entry: ConfigEntry | None) -> Iterable[Any]:
    """Iterate the parent entry's ConfigSubentry objects safely.

    HA stores ``entry.subentries`` as a ``MappingProxyType`` (NOT a
    plain ``dict``), so naive ``isinstance(subentries, dict)`` checks
    return False and code falls through to iterating the keys instead
    of the values — silently producing an empty list of subentries
    (G27). Use this helper everywhere instead of rolling your own.
    """
    if entry is None:
        return ()
    subs = getattr(entry, "subentries", None)
    if subs is None:
        return ()
    if isinstance(subs, Mapping):
        return tuple(subs.values())
    try:
        return tuple(subs)
    except TypeError:
        return ()


__all__ = [
    "SUBENTRY_FLOWS",
    "CategorySubentryFlow",
    "FieldSubentryFlow",
    "iter_subentries",
]
