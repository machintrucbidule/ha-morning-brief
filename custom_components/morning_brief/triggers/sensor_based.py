# rationale: implements a 5-state machine (idle / waiting / fired) plus the
# parallel daily-fallback timer, with three independent HA listener
# subscriptions (trigger sensor, opt-out sensors, daily fallback). The
# coordinated lifecycle is more readable kept together than split across
# files.
"""Sensor-based trigger (Section 16.2).

State machine:
- IDLE: waiting for the trigger sensor to enter ``trigger_to_state``.
- WAITING: countdown of ``delay_minutes`` running. Any opt-out state
  change short-circuits the wait and fires immediately.
- FIRED-TODAY: the user callback has run for today's calendar date.
  Resets after midnight (so a fresh trigger the next day starts a new
  cycle).

Plus a parallel daily fallback at ``fallback_hour`` that fires the
callback if no execution has happened that day yet.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any

import voluptuous as vol
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from ..const import DEFAULT_FALLBACK_HOUR, TRIGGER_SENSOR_BASED
from ..exceptions import ConfigurationError, TriggerError

_LOGGER = logging.getLogger(__name__)

TriggerCallback = Callable[[], Awaitable[None]]


class SensorBasedTrigger:
    """Trigger that fires after a sensor enters a state, with opt-out shortcut."""

    trigger_type = TRIGGER_SENSOR_BASED

    def __init__(
        self, hass: HomeAssistant, config: dict[str, Any], callback_: TriggerCallback
    ) -> None:
        self.hass = hass
        self.config = config
        self._callback = callback_
        self._unsub_trigger: Callable[[], None] | None = None
        self._unsub_optouts: Callable[[], None] | None = None
        self._unsub_fallback: Callable[[], None] | None = None
        self._cancel_delay: Callable[[], None] | None = None
        self._last_fired_date: date | None = None
        errors = self.validate_config()
        if errors:
            raise ConfigurationError(
                f"Invalid sensor_based trigger config: {errors}"
            )

    @property
    def trigger_entity_id(self) -> str:
        return str(self.config["trigger_entity_id"])

    @property
    def trigger_to_state(self) -> str:
        return str(self.config["trigger_to_state"])

    @property
    def delay_minutes(self) -> int:
        return int(self.config.get("delay_minutes", 30))

    @property
    def optout_entities(self) -> list[str]:
        return list(self.config.get("optout_entities", []))

    @property
    def fallback_hour(self) -> int:
        return int(self.config.get("fallback_hour", DEFAULT_FALLBACK_HOUR))

    @property
    def fallback_active(self) -> bool:
        return bool(self.config.get("fallback_active", True))

    async def async_setup(self) -> None:
        """Register listeners. Idempotent? No — call once."""
        if self._unsub_trigger is not None:
            raise TriggerError("SensorBasedTrigger is already set up")
        self._unsub_trigger = async_track_state_change_event(
            self.hass, [self.trigger_entity_id], self._on_trigger_event
        )
        if self.optout_entities:
            self._unsub_optouts = async_track_state_change_event(
                self.hass, self.optout_entities, self._on_optout_event
            )
        if self.fallback_active:
            self._unsub_fallback = async_track_time_change(
                self.hass,
                self._on_fallback_time,
                hour=self.fallback_hour,
                minute=0,
                second=0,
            )

    async def async_unload(self) -> None:
        """Cancel every listener and any pending delay."""
        for unsub_attr in ("_unsub_trigger", "_unsub_optouts", "_unsub_fallback"):
            unsub = getattr(self, unsub_attr)
            if unsub is not None:
                unsub()
                setattr(self, unsub_attr, None)
        self._cancel_pending_delay()

    def _cancel_pending_delay(self) -> None:
        if self._cancel_delay is not None:
            self._cancel_delay()
            self._cancel_delay = None

    @callback
    def _on_trigger_event(self, event: Event[EventStateChangedData]) -> None:
        """Trigger sensor state change → maybe start the delay."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state != self.trigger_to_state:
            return
        if self._already_fired_today():
            return
        self._cancel_pending_delay()
        self._cancel_delay = async_call_later(
            self.hass, self.delay_minutes * 60, self._on_delay_elapsed
        )

    @callback
    def _on_optout_event(self, event: Event[EventStateChangedData]) -> None:
        """Any opt-out sensor change during the delay → fire immediately."""
        if self._cancel_delay is None:
            return
        if self._already_fired_today():
            self._cancel_pending_delay()
            return
        self._cancel_pending_delay()
        self.hass.async_create_task(self._fire())

    async def _on_delay_elapsed(self, _now: datetime) -> None:
        """Delay countdown finished → fire."""
        self._cancel_delay = None
        await self._fire()

    async def _on_fallback_time(self, _now: datetime) -> None:
        """Daily fallback hour reached → fire if not already fired today."""
        if self._already_fired_today():
            return
        await self._fire()

    def _already_fired_today(self) -> bool:
        return self._last_fired_date == dt_util.now().date()

    async def _fire(self) -> None:
        """Invoke the user callback and record today as fired."""
        self._last_fired_date = dt_util.now().date()
        try:
            await self._callback()
        except Exception:  # noqa: BLE001 — entry-point boundary
            _LOGGER.exception("Sensor-based trigger callback failed")

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("trigger_entity_id"): str,
                vol.Required("trigger_to_state"): str,
                vol.Optional("delay_minutes", default=30): vol.All(
                    int, vol.Range(min=0)
                ),
                vol.Optional("optout_entities", default=list): [str],
                vol.Optional("fallback_hour", default=DEFAULT_FALLBACK_HOUR): vol.All(
                    int, vol.Range(min=0, max=23)
                ),
                vol.Optional("fallback_active", default=True): bool,
            }
        )

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self.config.get("trigger_entity_id"):
            errors.append("trigger_entity_id is required")
        if not self.config.get("trigger_to_state"):
            errors.append("trigger_to_state is required")
        delay = self.config.get("delay_minutes", 30)
        if not isinstance(delay, int) or delay < 0:
            errors.append("delay_minutes must be a non-negative int")
        hour = self.config.get("fallback_hour", DEFAULT_FALLBACK_HOUR)
        if not isinstance(hour, int) or not 0 <= hour <= 23:
            errors.append("fallback_hour must be an int in [0, 23]")
        opts = self.config.get("optout_entities", [])
        if not isinstance(opts, list) or not all(isinstance(e, str) for e in opts):
            errors.append("optout_entities must be a list of strings")
        return errors
