"""Manual logical-day strategy.

The logical date is held in instance state and only changes when
``advance_day`` is called (Phase 9 wires that into the
``morning_brief.advance_day`` service). On instance creation:
``logical_date = today, cal_offset = 0`` (Section 7.3).

Note: V1 keeps state in memory only — after a Home Assistant restart the
logical date resets to "today". This is acceptable per spec; persistent
state is a Phase 9+ enhancement.
"""

from __future__ import annotations

from datetime import date, datetime

import voluptuous as vol
from homeassistant.util import dt as dt_util

from ..const import LOGICAL_DAY_MANUAL
from .base import LogicalDayStrategy


class ManualStrategy(LogicalDayStrategy):
    """User-driven logical day. Advances only via the `advance_day` service."""

    strategy_type = LOGICAL_DAY_MANUAL

    def __init__(self, hass, config) -> None:  # type: ignore[no-untyped-def]
        super().__init__(hass, config)
        self._logical_date: date | None = None

    async def get_logical_date(self, now: datetime) -> tuple[date, int]:
        local_now = dt_util.as_local(now) if now.tzinfo else now
        today = local_now.date()
        if self._logical_date is None:
            self._logical_date = today
        cal_offset = (today - self._logical_date).days
        return self._logical_date, cal_offset

    def advance_day(self, today: date) -> date:
        """Advance the logical date to ``max(current, today)``.

        Returns the new logical_date. Called by the
        ``morning_brief.advance_day`` service (registered in Phase 9).
        """
        if self._logical_date is None or today > self._logical_date:
            self._logical_date = today
        return self._logical_date

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        # No params (Section 7.3).
        return vol.Schema({})

    def validate_config(self) -> list[str]:
        return []
