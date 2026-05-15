"""Fixed-cutoff logical-day strategy (default).

If ``now.hour >= cutoff_hour`` we're in today's logical day; otherwise we're
still in yesterday's. Works for the 90% of users who don't want anything
sleep-sensor-driven (Section 7.1).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import voluptuous as vol
from homeassistant.util import dt as dt_util

from ..const import DEFAULT_CUTOFF_HOUR, LOGICAL_DAY_FIXED_CUTOFF
from .base import LogicalDayStrategy


class FixedCutoffStrategy(LogicalDayStrategy):
    """Use a fixed local-time hour to define when "today" starts."""

    strategy_type = LOGICAL_DAY_FIXED_CUTOFF

    @property
    def cutoff_hour(self) -> int:
        return int(self.config.get("cutoff_hour", DEFAULT_CUTOFF_HOUR))

    async def get_logical_date(self, now: datetime) -> tuple[date, int]:
        """Compare local-time hour against the cutoff."""
        local_now = dt_util.as_local(now) if now.tzinfo else now
        if local_now.hour >= self.cutoff_hour:
            return local_now.date(), 0
        return local_now.date() - timedelta(days=1), 1

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional("cutoff_hour", default=DEFAULT_CUTOFF_HOUR): vol.All(
                    int, vol.Range(min=0, max=23)
                ),
            }
        )

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        cutoff = self.config.get("cutoff_hour", DEFAULT_CUTOFF_HOUR)
        if not isinstance(cutoff, int) or not 0 <= cutoff <= 23:
            errors.append("cutoff_hour must be an int in [0, 23]")
        return errors
