"""Instantaneous-value provider.

For sensors whose state is meaningful at any moment — resting HR, body
weight (continuous), outdoor temperature, etc. The "value of the day" is
either the daily mean (LTS) or the current state value (last).

See MORNING_BRIEF_SPEC.md Section 8.2.
"""

from __future__ import annotations

import logging
from datetime import date

import voluptuous as vol
from homeassistant.core import HomeAssistant

from ..const import (
    HISTORY_AGG_MEAN,
    PROVIDER_INSTANTANEOUS,
    STALE_NO_DATA,
    STALE_NO_DATA_FOR_DATE,
)
from ..history import HistoryQuery, query
from ..types import FieldValue
from .base import FieldProvider

_LOGGER = logging.getLogger(__name__)

_AGG_MEAN = "mean"
_AGG_LAST = "last"
_VALID_AGGREGATIONS: frozenset[str] = frozenset({_AGG_MEAN, _AGG_LAST})


class InstantaneousProvider(FieldProvider):
    """Provider for state-class=measurement style sensors."""

    provider_type = PROVIDER_INSTANTANEOUS

    @property
    def entity_id(self) -> str:
        return str(self.config["entity_id"])

    @property
    def aggregation(self) -> str:
        return str(self.config.get("aggregation", _AGG_MEAN))

    def _unit(self) -> str | None:
        state = self.hass.states.get(self.entity_id)
        if state is None:
            return None
        unit = state.attributes.get("unit_of_measurement")
        return str(unit) if unit is not None else None

    def _read_current_state(self) -> FieldValue:
        """Read the live state. None / unavailable / unknown / non-numeric → stale."""
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return FieldValue(
                raw=None, unit=self._unit(), stale=True, stale_reason=STALE_NO_DATA
            )
        try:
            raw = float(state.state)
        except (TypeError, ValueError):
            return FieldValue(
                raw=None, unit=self._unit(), stale=True, stale_reason=STALE_NO_DATA
            )
        return FieldValue(raw=raw, unit=self._unit(), as_of=state.last_updated)

    async def _historical_value(self, target_date: date) -> FieldValue:
        """LTS daily mean for the given date; stale if missing."""
        result = await query(
            self.hass,
            HistoryQuery(
                entity_id=self.entity_id,
                start_date=target_date,
                end_date=target_date,
                aggregation=HISTORY_AGG_MEAN,
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

    async def get_current_value(self, logical_date: date) -> FieldValue:
        """Aggregation-aware "today" value.

        ``last`` returns the live state directly. ``mean`` queries LTS for
        the logical day; if the bucket is missing (sensor without LTS, or
        not yet finalised), fall back to the live state.
        """
        if self.aggregation == _AGG_LAST:
            return self._read_current_state()
        result = await self._historical_value(logical_date)
        if result.raw is None:
            fallback = self._read_current_state()
            if fallback.raw is not None:
                return fallback
        return result

    async def get_value_for_date(self, target_date: date) -> FieldValue:
        """Past LTS daily mean only — no live-state fallback for past dates."""
        return await self._historical_value(target_date)

    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        """Per-day daily means over the inclusive range."""
        result = await query(
            self.hass,
            HistoryQuery(
                entity_id=self.entity_id,
                start_date=start_date,
                end_date=end_date,
                aggregation=HISTORY_AGG_MEAN,
            ),
        )
        unit = self._unit()
        out: dict[date, FieldValue] = {}
        for d, v in result.data.items():
            if v is None:
                out[d] = FieldValue(
                    raw=None, unit=unit, stale=True, stale_reason=STALE_NO_DATA_FOR_DATE
                )
            else:
                out[d] = FieldValue(raw=v, unit=unit)
        return out

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("entity_id"): str,
                vol.Optional("aggregation", default=_AGG_MEAN): vol.In(
                    sorted(_VALID_AGGREGATIONS)
                ),
                vol.Optional("window_hours_today", default=24): vol.All(
                    int, vol.Range(min=1, max=72)
                ),
            }
        )

    @classmethod
    def detect_from_entity(cls, hass: HomeAssistant, entity_id: str) -> float:
        state = hass.states.get(entity_id)
        if state is None:
            return 0.0
        if state.attributes.get("state_class") == "measurement":
            return 0.8
        try:
            float(state.state)
        except (TypeError, ValueError):
            return 0.0
        return 0.4

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self.config.get("entity_id"):
            errors.append("entity_id is required")
        agg = self.config.get("aggregation", _AGG_MEAN)
        if agg not in _VALID_AGGREGATIONS:
            errors.append(f"aggregation must be one of {sorted(_VALID_AGGREGATIONS)}")
        return errors
