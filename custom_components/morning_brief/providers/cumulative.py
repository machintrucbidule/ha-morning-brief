"""Cumulative-counter provider.

For sensors whose value increases throughout a period and resets at a known
hour. The "value of the day" is the increase between two consecutive resets,
which the recorder exposes natively as the LTS ``change`` statistic.

Use cases: daily steps, daily kWh, daily sleep total, daily water.

See MORNING_BRIEF_SPEC.md Section 8.1.
"""

from __future__ import annotations

import logging
from datetime import date

import voluptuous as vol
from homeassistant.core import HomeAssistant

from ..const import (
    HISTORY_AGG_CHANGE,
    PROVIDER_CUMULATIVE,
    STALE_NO_DATA_FOR_DATE,
)
from ..history import HistoryQuery, query
from ..types import FieldValue
from .base import FieldProvider

_LOGGER = logging.getLogger(__name__)


class CumulativeProvider(FieldProvider):
    """Provider for total_increasing / total style sensors."""

    provider_type = PROVIDER_CUMULATIVE

    @property
    def entity_id(self) -> str:
        return str(self.config["entity_id"])

    @property
    def reset_hour(self) -> int:
        return int(self.config.get("reset_hour", 0))

    def _unit(self) -> str | None:
        state = self.hass.states.get(self.entity_id)
        if state is None:
            return None
        unit = state.attributes.get("unit_of_measurement")
        return str(unit) if unit is not None else None

    async def _change_for_date(self, target_date: date) -> FieldValue:
        """Return the LTS ``change`` for one day; stale if missing."""
        result = await query(
            self.hass,
            HistoryQuery(
                entity_id=self.entity_id,
                start_date=target_date,
                end_date=target_date,
                aggregation=HISTORY_AGG_CHANGE,
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
        """LTS change for today (may be partial — bucket finalises at reset)."""
        return await self._change_for_date(logical_date)

    async def get_value_for_date(self, target_date: date) -> FieldValue:
        return await self._change_for_date(target_date)

    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        result = await query(
            self.hass,
            HistoryQuery(
                entity_id=self.entity_id,
                start_date=start_date,
                end_date=end_date,
                aggregation=HISTORY_AGG_CHANGE,
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
                vol.Optional("reset_hour", default=0): vol.All(
                    int, vol.Range(min=0, max=23)
                ),
            }
        )

    @classmethod
    def detect_from_entity(cls, hass: HomeAssistant, entity_id: str) -> float:
        state = hass.states.get(entity_id)
        if state is None:
            return 0.0
        state_class = state.attributes.get("state_class")
        if state_class == "total_increasing":
            return 0.9
        device_class = state.attributes.get("device_class")
        if state_class == "total" and device_class in {"energy", "water", "gas"}:
            return 0.7
        return 0.0

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self.config.get("entity_id"):
            errors.append("entity_id is required")
        reset_hour = self.config.get("reset_hour", 0)
        if not isinstance(reset_hour, int) or not 0 <= reset_hour <= 23:
            errors.append("reset_hour must be an int in [0, 23]")
        return errors
