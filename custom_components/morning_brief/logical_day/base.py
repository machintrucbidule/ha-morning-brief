"""LogicalDayStrategy ABC.

Concrete strategies decide which calendar date the brief is "about" from
the user's subjective perspective. They return ``(logical_date, cal_offset)``
where ``cal_offset == 0`` means the logical date matches today's calendar
date and ``cal_offset == 1`` means the user has not yet transitioned to
today (the brief is about yesterday).

See MORNING_BRIEF_SPEC.md Section 7.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant

__all__ = ["LogicalDayStrategy"]


class LogicalDayStrategy(ABC):
    """Abstract base for every logical-day strategy (D6)."""

    strategy_type: str  # set as class attribute by each subclass

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Bind the strategy to an HA instance and a per-instance config."""
        self.hass = hass
        self.config = config

    @abstractmethod
    async def get_logical_date(self, now: datetime) -> tuple[date, int]:
        """Return ``(logical_date, cal_offset)`` given the current time."""

    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> vol.Schema:
        """Return a voluptuous schema for the strategy-specific config block."""

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Return a list of human-readable errors; empty if the config is valid."""
