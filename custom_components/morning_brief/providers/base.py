"""FieldProvider ABC.

Every concrete provider in this package inherits this class and implements
its three async data methods + the config schema + `validate_config`. The
factory in ``providers/__init__.py`` rejects any subclass whose
``validate_config`` returns errors (R5).

See MORNING_BRIEF_SPEC.md Sections 8 + 41.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant

from ..types import FieldValue

__all__ = ["FieldProvider", "FieldValue"]


class FieldProvider(ABC):
    """Abstract base for every field provider type.

    Concrete subclasses MUST set the ``provider_type`` class attribute
    to one of the closed-list values in ``const.PROVIDER_TYPES``.
    """

    provider_type: str  # set as class attribute by each subclass

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Bind the provider to a HA instance and a per-field config dict."""
        self.hass = hass
        self.config = config

    @abstractmethod
    async def get_current_value(self, logical_date: date) -> FieldValue:
        """Return the field value for the brief's logical date ("today")."""

    @abstractmethod
    async def get_value_for_date(self, target_date: date) -> FieldValue:
        """Return the field value for an arbitrary past date."""

    @abstractmethod
    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        """Return one ``FieldValue`` per day in the inclusive date range."""

    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> vol.Schema:
        """Return a voluptuous schema for the provider-specific config block."""

    @classmethod
    def detect_from_entity(
        cls, hass: HomeAssistant, entity_id: str
    ) -> float:
        """Return a confidence score 0.0–1.0 that this provider fits ``entity_id``.

        Default 0. Subclasses override with a heuristic (Section 8.x).
        """
        return 0.0

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Return a list of human-readable errors; empty if the config is valid."""
