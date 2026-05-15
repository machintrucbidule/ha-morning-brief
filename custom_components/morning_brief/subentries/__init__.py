"""Subentry registry (D3, Section 21).

Two subentry types: `field` (sensor + display + comparisons + anomaly
config) and `category` (display grouping). Each has its own
SubentryFlowHandler exposed via the integration's manifest
``supported_subentry_types`` list.
"""

from __future__ import annotations

from .category.flow import CategorySubentryFlow
from .field.flow import FieldSubentryFlow

SUBENTRY_FLOWS = {
    "field": FieldSubentryFlow,
    "category": CategorySubentryFlow,
}

__all__ = ["SUBENTRY_FLOWS", "CategorySubentryFlow", "FieldSubentryFlow"]
