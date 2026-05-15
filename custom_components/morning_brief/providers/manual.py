"""Manual-input provider.

Reads ``input_number.*``, ``input_text.*`` or ``input_datetime.*`` entities
that the user maintains by hand. The "value" is just the entity state,
typed according to ``value_type``.

See MORNING_BRIEF_SPEC.md Section 8.8.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    HISTORY_AGG_LAST,
    PROVIDER_MANUAL,
    STALE_NO_DATA,
    STALE_NO_DATA_FOR_DATE,
)
from ..history import HistoryQuery, query
from ..types import FieldValue
from .base import FieldProvider

_LOGGER = logging.getLogger(__name__)

_VALUE_NUMBER = "number"
_VALUE_TEXT = "text"
_VALUE_DATETIME = "datetime"
_VALUE_TYPES: frozenset[str] = frozenset({_VALUE_NUMBER, _VALUE_TEXT, _VALUE_DATETIME})


def _detect_value_type(entity_id: str) -> str:
    """Map an `input_*.*` entity prefix to a default value_type."""
    if entity_id.startswith("input_number."):
        return _VALUE_NUMBER
    if entity_id.startswith("input_datetime."):
        return _VALUE_DATETIME
    return _VALUE_TEXT


def _coerce(state: str, value_type: str) -> Any:
    """Parse the raw state into the configured Python type. None on failure."""
    if value_type == _VALUE_NUMBER:
        try:
            return float(state)
        except (TypeError, ValueError):
            return None
    if value_type == _VALUE_DATETIME:
        return dt_util.parse_datetime(state)
    return state


class ManualProvider(FieldProvider):
    """Provider for `input_number` / `input_text` / `input_datetime`."""

    provider_type = PROVIDER_MANUAL

    @property
    def entity_id(self) -> str:
        return str(self.config["entity_id"])

    @property
    def value_type(self) -> str:
        return str(self.config.get("value_type") or _detect_value_type(self.entity_id))

    def _unit(self) -> str | None:
        state = self.hass.states.get(self.entity_id)
        if state is None:
            return None
        unit = state.attributes.get("unit_of_measurement")
        return str(unit) if unit is not None else None

    def _read_state(self) -> FieldValue:
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return FieldValue(
                raw=None, unit=self._unit(), stale=True, stale_reason=STALE_NO_DATA
            )
        coerced = _coerce(state.state, self.value_type)
        if coerced is None:
            return FieldValue(
                raw=None, unit=self._unit(), stale=True, stale_reason=STALE_NO_DATA
            )
        # Datetime values stringify into FieldValue.raw via isoformat for transport.
        raw: float | int | str = (
            coerced.isoformat() if isinstance(coerced, datetime) else coerced
        )
        return FieldValue(raw=raw, unit=self._unit(), as_of=state.last_updated)

    async def get_current_value(self, logical_date: date) -> FieldValue:
        return self._read_state()

    async def get_value_for_date(self, target_date: date) -> FieldValue:
        """For numeric inputs use LTS ``last``; otherwise return None."""
        if self.value_type != _VALUE_NUMBER:
            return FieldValue(
                raw=None,
                unit=self._unit(),
                stale=True,
                stale_reason=STALE_NO_DATA_FOR_DATE,
            )
        result = await query(
            self.hass,
            HistoryQuery(
                entity_id=self.entity_id,
                start_date=target_date,
                end_date=target_date,
                aggregation=HISTORY_AGG_LAST,
            ),
        )
        value = result.data.get(target_date)
        if value is None:
            return FieldValue(
                raw=None,
                unit=self._unit(),
                stale=True,
                stale_reason=STALE_NO_DATA_FOR_DATE,
            )
        return FieldValue(raw=value, unit=self._unit())

    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        if self.value_type != _VALUE_NUMBER:
            cur = start_date
            unit = self._unit()
            out: dict[date, FieldValue] = {}
            while cur <= end_date:
                out[cur] = FieldValue(
                    raw=None,
                    unit=unit,
                    stale=True,
                    stale_reason=STALE_NO_DATA_FOR_DATE,
                )
                cur = date.fromordinal(cur.toordinal() + 1)
            return out

        result = await query(
            self.hass,
            HistoryQuery(
                entity_id=self.entity_id,
                start_date=start_date,
                end_date=end_date,
                aggregation=HISTORY_AGG_LAST,
            ),
        )
        unit = self._unit()
        out_num: dict[date, FieldValue] = {}
        for d, v in result.data.items():
            if v is None:
                out_num[d] = FieldValue(
                    raw=None, unit=unit, stale=True, stale_reason=STALE_NO_DATA_FOR_DATE
                )
            else:
                out_num[d] = FieldValue(raw=v, unit=unit)
        return out_num

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("entity_id"): str,
                vol.Optional("value_type"): vol.In(sorted(_VALUE_TYPES)),
            }
        )

    @classmethod
    def detect_from_entity(cls, hass: HomeAssistant, entity_id: str) -> float:
        if entity_id.startswith("input_number."):
            return 0.8
        if entity_id.startswith("input_text.") or entity_id.startswith("input_datetime."):
            return 0.6
        return 0.0

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        eid = self.config.get("entity_id")
        if not eid:
            errors.append("entity_id is required")
        elif not (
            eid.startswith("input_number.")
            or eid.startswith("input_text.")
            or eid.startswith("input_datetime.")
        ):
            errors.append("entity_id must be an input_number/input_text/input_datetime")
        if "value_type" in self.config and self.config["value_type"] not in _VALUE_TYPES:
            errors.append(f"value_type must be one of {sorted(_VALUE_TYPES)}")
        return errors
