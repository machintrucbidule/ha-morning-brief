"""Event-based provider.

For sensors that only change on a discrete user/device event — body weight
from a Wi-Fi scale, manual readings, etc. The "value of the day" is the
last valid event whose timestamp falls inside the logical day; if none, we
return the most recent prior event with ``stale_reason=no_event_today``.

Filtering follows D23 + G1: never use `last_updated`, drop unavailable /
unknown, dedupe within ``epsilon``, debounce within ``min_debounce``.

See MORNING_BRIEF_SPEC.md Section 8.3.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    DEFAULT_EVENT_EPSILON,
    PROVIDER_EVENT_BASED,
    STALE_NO_DATA,
    STALE_NO_EVENT_TODAY,
)
from ..history import StateChange, filter_valid_changes, get_short_term
from ..types import FieldValue
from .base import FieldProvider

_LOGGER = logging.getLogger(__name__)

_DEFAULT_LOOKBACK_DAYS = 30
_DEFAULT_MIN_DEBOUNCE_MINUTES = 5


class EventBasedProvider(FieldProvider):
    """Provider for sparse event-driven sensors (e.g., body-weight scale)."""

    provider_type = PROVIDER_EVENT_BASED

    @property
    def entity_id(self) -> str:
        return str(self.config["entity_id"])

    @property
    def epsilon(self) -> float:
        return float(self.config.get("epsilon", DEFAULT_EVENT_EPSILON))

    @property
    def min_debounce_seconds(self) -> int:
        minutes = int(self.config.get("min_debounce_minutes", _DEFAULT_MIN_DEBOUNCE_MINUTES))
        return minutes * 60

    def _unit(self) -> str | None:
        state = self.hass.states.get(self.entity_id)
        if state is None:
            return None
        unit = state.attributes.get("unit_of_measurement")
        return str(unit) if unit is not None else None

    async def _filtered_events(self, end_dt: datetime, lookback_days: int) -> list[StateChange]:
        """Return clean event sequence ending at ``end_dt``."""
        start_dt = end_dt - timedelta(days=lookback_days)
        try:
            raw_changes = await get_short_term(
                self.hass, self.entity_id, start_dt, end_dt
            )
        except Exception:  # noqa: BLE001 — defensive at the provider boundary
            return []
        return filter_valid_changes(
            raw_changes,
            epsilon=self.epsilon,
            min_debounce_seconds=self.min_debounce_seconds,
        )

    @staticmethod
    def _to_float(s: str) -> float | None:
        try:
            return float(s)
        except (TypeError, ValueError):
            return None

    async def get_current_value(self, logical_date: date) -> FieldValue:
        """Last event in the logical day, or most-recent-prior + stale flag."""
        end_dt = dt_util.start_of_local_day(logical_date) + timedelta(days=1)
        events = await self._filtered_events(end_dt, _DEFAULT_LOOKBACK_DAYS)
        if not events:
            return FieldValue(
                raw=None, unit=self._unit(), stale=True, stale_reason=STALE_NO_DATA
            )
        last = events[-1]
        local_day = dt_util.as_local(last.timestamp).date()
        raw = self._to_float(last.state)
        if local_day == logical_date:
            return FieldValue(raw=raw, unit=self._unit(), as_of=last.timestamp)
        return FieldValue(
            raw=raw,
            unit=self._unit(),
            stale=True,
            stale_reason=STALE_NO_EVENT_TODAY,
            as_of=last.timestamp,
        )

    async def get_value_for_date(self, target_date: date) -> FieldValue:
        """Most-recent valid event with timestamp ≤ end of ``target_date``."""
        end_dt = dt_util.start_of_local_day(target_date) + timedelta(days=1)
        events = await self._filtered_events(end_dt, _DEFAULT_LOOKBACK_DAYS)
        if not events:
            return FieldValue(
                raw=None, unit=self._unit(), stale=True, stale_reason=STALE_NO_DATA
            )
        last = events[-1]
        return FieldValue(
            raw=self._to_float(last.state),
            unit=self._unit(),
            as_of=last.timestamp,
        )

    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        """For each date, the last event with timestamp ≤ end of that date."""
        out: dict[date, FieldValue] = {}
        cur = start_date
        unit = self._unit()
        while cur <= end_date:
            end_dt = dt_util.start_of_local_day(cur) + timedelta(days=1)
            events = await self._filtered_events(end_dt, _DEFAULT_LOOKBACK_DAYS)
            if events:
                last = events[-1]
                out[cur] = FieldValue(
                    raw=self._to_float(last.state),
                    unit=unit,
                    as_of=last.timestamp,
                )
            else:
                out[cur] = FieldValue(
                    raw=None, unit=unit, stale=True, stale_reason=STALE_NO_DATA
                )
            cur = date.fromordinal(cur.toordinal() + 1)
        return out

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("entity_id"): str,
                vol.Optional("epsilon", default=DEFAULT_EVENT_EPSILON): vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                ),
                vol.Optional(
                    "min_debounce_minutes", default=_DEFAULT_MIN_DEBOUNCE_MINUTES
                ): vol.All(int, vol.Range(min=0)),
            }
        )

    @classmethod
    def detect_from_entity(cls, hass: HomeAssistant, entity_id: str) -> float:
        state = hass.states.get(entity_id)
        if state is None:
            return 0.0
        if state.attributes.get("state_class") is not None:
            return 0.0
        device_class = state.attributes.get("device_class")
        if device_class in {"weight", "mass"}:
            return 0.7
        return 0.0

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self.config.get("entity_id"):
            errors.append("entity_id is required")
        try:
            if float(self.config.get("epsilon", DEFAULT_EVENT_EPSILON)) < 0:
                errors.append("epsilon must be ≥ 0")
        except (TypeError, ValueError):
            errors.append("epsilon must be a number")
        debounce = self.config.get("min_debounce_minutes", _DEFAULT_MIN_DEBOUNCE_MINUTES)
        if not isinstance(debounce, int) or debounce < 0:
            errors.append("min_debounce_minutes must be a non-negative int")
        return errors


# `time` is reserved for future windowed sub-day aggregations; silence unused.
_ = time
