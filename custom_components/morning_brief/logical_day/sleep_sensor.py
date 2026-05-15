"""Sleep-sensor-driven logical-day strategy.

Reads the configured `binary_sensor.*`'s recent transitions to find the
most recent wake-up event (transition to ``awake_state``). The logical
date is the calendar day containing the start of the night that just
ended. If no usable transition is found within ``lookback_hours``, fall
back to the fixed_cutoff logic with ``hard_fallback_hour``.

Edge cases addressed (Section 7.2):
- Naps: ignore wake transitions where the prior asleep period is shorter
  than ``min_sleep_duration_minutes`` (default 120).
- Sensor unavailable / missing: hard fallback engages.
- All-nighter (no transition in 36h): hard fallback engages.
- Multiple wake transitions in the window: use the most recent one.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.util import dt as dt_util

from ..const import (
    DEFAULT_HARD_FALLBACK_HOUR,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_MIN_SLEEP_DURATION_MINUTES,
    LOGICAL_DAY_SLEEP_SENSOR,
)
from ..history import StateChange, get_short_term
from .base import LogicalDayStrategy

_LOGGER = logging.getLogger(__name__)


class SleepSensorStrategy(LogicalDayStrategy):
    """Logical day driven by an actual wake-up event."""

    strategy_type = LOGICAL_DAY_SLEEP_SENSOR

    @property
    def sleep_sensor_entity(self) -> str:
        return str(self.config["sleep_sensor_entity"])

    @property
    def awake_state(self) -> str:
        return str(self.config.get("awake_state", "off"))

    @property
    def hard_fallback_hour(self) -> int:
        return int(self.config.get("hard_fallback_hour", DEFAULT_HARD_FALLBACK_HOUR))

    @property
    def lookback_hours(self) -> int:
        return int(self.config.get("lookback_hours", DEFAULT_LOOKBACK_HOURS))

    @property
    def min_sleep_duration_minutes(self) -> int:
        return int(
            self.config.get(
                "min_sleep_duration_minutes", DEFAULT_MIN_SLEEP_DURATION_MINUTES
            )
        )

    def _hard_fallback(self, now_local: datetime) -> tuple[date, int]:
        if now_local.hour >= self.hard_fallback_hour:
            return now_local.date(), 0
        return now_local.date() - timedelta(days=1), 1

    @staticmethod
    def _last_qualifying_wake(
        changes: list[StateChange],
        awake_state: str,
        min_sleep_duration_minutes: int,
    ) -> StateChange | None:
        """Return the most recent transition INTO awake_state qualified as a real wake.

        A "real wake" is preceded by an asleep period of at least
        ``min_sleep_duration_minutes``. Transitions that don't follow a
        long-enough asleep period are nap exits and are ignored.
        """
        last_asleep_start: datetime | None = None
        last_state: str | None = None
        candidate: StateChange | None = None
        min_delta = timedelta(minutes=min_sleep_duration_minutes)

        for change in changes:
            if change.state == awake_state:
                if (
                    last_state is not None
                    and last_state != awake_state
                    and last_asleep_start is not None
                    and (change.timestamp - last_asleep_start) >= min_delta
                ):
                    candidate = change
                last_state = awake_state
            else:
                if last_state != change.state:
                    last_asleep_start = change.timestamp
                last_state = change.state
        return candidate

    async def get_logical_date(self, now: datetime) -> tuple[date, int]:
        local_now = dt_util.as_local(now) if now.tzinfo else now
        start_dt = local_now - timedelta(hours=self.lookback_hours)
        try:
            changes = await get_short_term(
                self.hass, self.sleep_sensor_entity, start_dt, local_now
            )
        except Exception:  # noqa: BLE001 — defensive at strategy boundary
            _LOGGER.exception(
                "Sleep sensor lookup failed for %s — using hard fallback",
                self.sleep_sensor_entity,
            )
            return self._hard_fallback(local_now)

        wake = self._last_qualifying_wake(
            changes, self.awake_state, self.min_sleep_duration_minutes
        )
        if wake is None:
            return self._hard_fallback(local_now)

        # The night that ended at `wake.timestamp` belongs to the calendar day
        # that started before midnight — i.e. four hours earlier suffices to
        # land in the right day for typical sleep schedules.
        anchor = wake.timestamp - timedelta(hours=4)
        logical_date = dt_util.as_local(anchor).date()
        cal_offset = (local_now.date() - logical_date).days
        return logical_date, cal_offset

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("sleep_sensor_entity"): str,
                vol.Optional("awake_state", default="off"): str,
                vol.Optional(
                    "hard_fallback_hour", default=DEFAULT_HARD_FALLBACK_HOUR
                ): vol.All(int, vol.Range(min=0, max=23)),
                vol.Optional("lookback_hours", default=DEFAULT_LOOKBACK_HOURS): vol.All(
                    int, vol.Range(min=1, max=72)
                ),
                vol.Optional(
                    "min_sleep_duration_minutes",
                    default=DEFAULT_MIN_SLEEP_DURATION_MINUTES,
                ): vol.All(int, vol.Range(min=0)),
            }
        )

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        eid = self.config.get("sleep_sensor_entity")
        if not eid:
            errors.append("sleep_sensor_entity is required")
        elif not eid.startswith("binary_sensor."):
            errors.append("sleep_sensor_entity must be a binary_sensor.* entity")
        if not isinstance(self.config.get("awake_state", "off"), str):
            errors.append("awake_state must be a string")
        hour = self.config.get("hard_fallback_hour", DEFAULT_HARD_FALLBACK_HOUR)
        if not isinstance(hour, int) or not 0 <= hour <= 23:
            errors.append("hard_fallback_hour must be an int in [0, 23]")
        return errors


# Silence unused-import if Any not referenced (kept for type widening).
_ = Any
