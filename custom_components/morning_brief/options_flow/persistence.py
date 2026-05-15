"""Persistence section schema (Section 20, D16)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from ..const import DEFAULT_RETENTION, MAX_RETENTION, MIN_RETENTION


def persistence_schema(current: dict[str, Any]) -> vol.Schema:
    prev = current.get("persistence", {})
    return vol.Schema(
        {
            vol.Optional(
                "retention", default=prev.get("retention", DEFAULT_RETENTION)
            ): vol.All(int, vol.Range(min=MIN_RETENTION, max=MAX_RETENTION)),
        }
    )
