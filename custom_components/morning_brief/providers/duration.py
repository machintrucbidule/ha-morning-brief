"""Duration-since-event provider.

Computes ``end_of_logical_day - reference_timestamp`` (in seconds) where
the reference comes from one of:
- ``input_datetime``: the entity state itself is the timestamp.
- ``sensor_last_changed``: the wrapped sensor's `last_changed`.
- ``sensor_attribute_datetime``: a datetime stored in an attribute.

See MORNING_BRIEF_SPEC.md Section 8.5.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import PROVIDER_DURATION, STALE_NO_DATA
from ..types import FieldValue
from .base import FieldProvider

_LOGGER = logging.getLogger(__name__)

_SOURCE_INPUT_DATETIME = "input_datetime"
_SOURCE_SENSOR_LAST_CHANGED = "sensor_last_changed"
_SOURCE_SENSOR_ATTR_DT = "sensor_attribute_datetime"
_SOURCE_TYPES: frozenset[str] = frozenset(
    {_SOURCE_INPUT_DATETIME, _SOURCE_SENSOR_LAST_CHANGED, _SOURCE_SENSOR_ATTR_DT}
)

_UNIT_AUTO = "auto"
_UNIT_DAYS = "days"
_UNIT_HOURS = "hours"
_UNIT_MINUTES = "minutes"
_DISPLAY_UNITS: frozenset[str] = frozenset(
    {_UNIT_AUTO, _UNIT_DAYS, _UNIT_HOURS, _UNIT_MINUTES}
)


def _parse_dt(value: str | datetime | None) -> datetime | None:
    """Parse a datetime-or-string into a tz-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt_util.UTC)
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_util.UTC)


class DurationProvider(FieldProvider):
    """Provider for "time since X" fields."""

    provider_type = PROVIDER_DURATION

    @property
    def source_type(self) -> str:
        return str(self.config["source_type"])

    @property
    def entity_id(self) -> str:
        return str(self.config["entity_id"])

    @property
    def attribute_name(self) -> str | None:
        return self.config.get("attribute_name")

    @property
    def display_unit(self) -> str:
        return str(self.config.get("display_unit", _UNIT_AUTO))

    def _resolve_reference(self) -> datetime | None:
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        if self.source_type == _SOURCE_INPUT_DATETIME:
            return _parse_dt(state.state)
        if self.source_type == _SOURCE_SENSOR_LAST_CHANGED:
            return state.last_changed
        if self.source_type == _SOURCE_SENSOR_ATTR_DT:
            attr_name = self.attribute_name or ""
            attr = state.attributes.get(attr_name)
            return _parse_dt(attr)
        return None

    def _seconds_to_unit(self, seconds: float) -> tuple[float, str]:
        """Convert a non-negative seconds value into the configured display unit."""
        if self.display_unit == _UNIT_DAYS:
            return seconds / 86400, _UNIT_DAYS
        if self.display_unit == _UNIT_HOURS:
            return seconds / 3600, _UNIT_HOURS
        if self.display_unit == _UNIT_MINUTES:
            return seconds / 60, _UNIT_MINUTES
        # auto: pick the most readable unit
        if seconds >= 86400:
            return seconds / 86400, _UNIT_DAYS
        if seconds >= 3600:
            return seconds / 3600, _UNIT_HOURS
        return seconds / 60, _UNIT_MINUTES

    def _value_at(self, target_date: date) -> FieldValue:
        ref = self._resolve_reference()
        if ref is None:
            return FieldValue(
                raw=None, unit=self.display_unit, stale=True, stale_reason=STALE_NO_DATA
            )
        end_of_day = dt_util.start_of_local_day(target_date) + timedelta(days=1)
        elapsed = (end_of_day - ref).total_seconds()
        if elapsed < 0:
            _LOGGER.debug(
                "Reference timestamp in the future for %s — clamping to 0",
                self.entity_id,
            )
            elapsed = 0.0
        value, unit = self._seconds_to_unit(elapsed)
        return FieldValue(raw=value, unit=unit, as_of=ref)

    async def get_current_value(self, logical_date: date) -> FieldValue:
        return self._value_at(logical_date)

    async def get_value_for_date(self, target_date: date) -> FieldValue:
        return self._value_at(target_date)

    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        out: dict[date, FieldValue] = {}
        cur = start_date
        while cur <= end_date:
            out[cur] = self._value_at(cur)
            cur = date.fromordinal(cur.toordinal() + 1)
        return out

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("source_type"): vol.In(sorted(_SOURCE_TYPES)),
                vol.Required("entity_id"): str,
                vol.Optional("attribute_name"): str,
                vol.Optional("display_unit", default=_UNIT_AUTO): vol.In(
                    sorted(_DISPLAY_UNITS)
                ),
                vol.Optional("min_debounce_minutes", default=5): vol.All(
                    int, vol.Range(min=0)
                ),
            }
        )

    @classmethod
    def detect_from_entity(cls, hass: HomeAssistant, entity_id: str) -> float:
        if entity_id.startswith("input_datetime."):
            return 0.7
        return 0.0

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        st = self.config.get("source_type")
        if st not in _SOURCE_TYPES:
            errors.append(f"source_type must be one of {sorted(_SOURCE_TYPES)}")
        if not self.config.get("entity_id"):
            errors.append("entity_id is required")
        if st == _SOURCE_SENSOR_ATTR_DT and not self.config.get("attribute_name"):
            errors.append("attribute_name is required when source_type=sensor_attribute_datetime")
        unit = self.config.get("display_unit", _UNIT_AUTO)
        if unit not in _DISPLAY_UNITS:
            errors.append(f"display_unit must be one of {sorted(_DISPLAY_UNITS)}")
        return errors
