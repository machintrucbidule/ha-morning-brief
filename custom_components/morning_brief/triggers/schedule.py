"""Schedule (cron-style) trigger.

Fires the supplied callback at a configured local-time HH:MM on each of
the configured days_of_week. Days follow the ISO convention 0=Monday …
6=Sunday (Section 16.1).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from ..const import TRIGGER_SCHEDULE
from ..exceptions import ConfigurationError, TriggerError

_LOGGER = logging.getLogger(__name__)

TriggerCallback = Callable[[], Awaitable[None]]


class ScheduleTrigger:
    """Cron-style time trigger driven by `async_track_time_change`."""

    trigger_type = TRIGGER_SCHEDULE

    def __init__(
        self, hass: HomeAssistant, config: dict[str, Any], callback: TriggerCallback
    ) -> None:
        self.hass = hass
        self.config = config
        self._callback = callback
        self._unsub: Callable[[], None] | None = None
        errors = self.validate_config()
        if errors:
            raise ConfigurationError(
                f"Invalid schedule trigger config: {errors}"
            )

    @property
    def time(self) -> str:
        return str(self.config["time"])

    @property
    def days_of_week(self) -> list[int]:
        return list(self.config.get("days_of_week", list(range(7))))

    @property
    def hour(self) -> int:
        return int(self.time.split(":")[0])

    @property
    def minute(self) -> int:
        parts = self.time.split(":")
        return int(parts[1]) if len(parts) > 1 else 0

    async def async_setup(self) -> None:
        """Register the time listener. Call once during entry setup."""
        if self._unsub is not None:
            raise TriggerError("ScheduleTrigger is already set up")
        self._unsub = async_track_time_change(
            self.hass,
            self._on_fire,
            hour=self.hour,
            minute=self.minute,
            second=0,
        )

    async def async_unload(self) -> None:
        """Detach the time listener."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _on_fire(self, now: datetime) -> None:
        """Time listener — invoke the user callback if today is configured."""
        weekday = now.weekday()
        if weekday not in self.days_of_week:
            return
        try:
            await self._callback()
        except Exception:  # noqa: BLE001 — entry-point boundary; never crash HA
            _LOGGER.exception("Schedule trigger callback failed")

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("time"): vol.Match(r"^\d{1,2}:\d{2}$"),
                vol.Optional("days_of_week", default=list(range(7))): [
                    vol.All(int, vol.Range(min=0, max=6))
                ],
            }
        )

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        time = self.config.get("time")
        if not isinstance(time, str) or ":" not in time:
            errors.append("time must be 'HH:MM'")
        else:
            try:
                hour, minute = time.split(":")
                h, m = int(hour), int(minute)
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    errors.append("time hour/minute out of range")
            except (TypeError, ValueError):
                errors.append("time must parse as HH:MM")
        days = self.config.get("days_of_week", list(range(7)))
        if not isinstance(days, list) or not all(
            isinstance(d, int) and 0 <= d <= 6 for d in days
        ):
            errors.append("days_of_week must be a list of ints in [0, 6]")
        return errors
