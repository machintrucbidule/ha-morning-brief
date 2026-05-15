"""State / enum provider.

For sensors whose value is a state name or enum (binary_sensor, electricity
tariff color, presence, workday). Optional ``state_mapping`` lets the user
attach a label / icon / color to each known state value.

See MORNING_BRIEF_SPEC.md Section 8.4.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import PROVIDER_STATE, STALE_NO_DATA, STALE_NO_DATA_FOR_DATE
from ..history import get_short_term
from ..types import FieldValue
from .base import FieldProvider

_LOGGER = logging.getLogger(__name__)


class StateProvider(FieldProvider):
    """Provider for non-numeric state sensors."""

    provider_type = PROVIDER_STATE

    @property
    def entity_id(self) -> str:
        return str(self.config["entity_id"])

    @property
    def state_mapping(self) -> dict[str, dict[str, Any]]:
        return dict(self.config.get("state_mapping") or {})

    def _decorate(self, raw: str | None) -> dict[str, Any]:
        """Return the mapping entry for ``raw`` or an empty dict."""
        if raw is None:
            return {}
        mapping = self.state_mapping.get(raw)
        return dict(mapping) if mapping else {}

    def _build_field_value(
        self,
        raw: str | None,
        as_of: datetime | None,
        stale: bool,
        stale_reason: str | None,
    ) -> FieldValue:
        return FieldValue(
            raw=raw,
            unit=None,
            stale=stale,
            stale_reason=stale_reason,
            as_of=as_of,
            extra={"mapping": self._decorate(raw)} if raw is not None else {},
        )

    async def get_current_value(self, logical_date: date) -> FieldValue:
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return self._build_field_value(
                raw=None, as_of=None, stale=True, stale_reason=STALE_NO_DATA
            )
        return self._build_field_value(
            raw=state.state,
            as_of=state.last_updated,
            stale=False,
            stale_reason=None,
        )

    async def _state_at_end_of_day(self, target_date: date) -> FieldValue:
        """Last recorder state with timestamp ≤ end-of-local-day for ``target_date``."""
        end_dt = dt_util.start_of_local_day(target_date) + timedelta(days=1)
        # 30-day lookback covers most "what was the state last Tuesday" needs.
        start_dt = datetime.combine(
            target_date - timedelta(days=30), time.min, tzinfo=end_dt.tzinfo
        )
        try:
            changes = await get_short_term(self.hass, self.entity_id, start_dt, end_dt)
        except Exception:  # noqa: BLE001 — defensive at the provider boundary
            return self._build_field_value(
                raw=None, as_of=None, stale=True, stale_reason=STALE_NO_DATA_FOR_DATE
            )

        valid = [c for c in changes if c.state not in ("unavailable", "unknown")]
        if not valid:
            return self._build_field_value(
                raw=None, as_of=None, stale=True, stale_reason=STALE_NO_DATA_FOR_DATE
            )
        last = valid[-1]
        return self._build_field_value(
            raw=last.state,
            as_of=last.timestamp,
            stale=False,
            stale_reason=None,
        )

    async def get_value_for_date(self, target_date: date) -> FieldValue:
        return await self._state_at_end_of_day(target_date)

    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        out: dict[date, FieldValue] = {}
        cur = start_date
        while cur <= end_date:
            out[cur] = await self._state_at_end_of_day(cur)
            cur = date.fromordinal(cur.toordinal() + 1)
        return out

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("entity_id"): str,
                vol.Optional("state_mapping"): dict,
            }
        )

    @classmethod
    def detect_from_entity(cls, hass: HomeAssistant, entity_id: str) -> float:
        if entity_id.startswith("binary_sensor."):
            return 0.5
        state = hass.states.get(entity_id)
        if state is None:
            return 0.0
        try:
            float(state.state)
        except (TypeError, ValueError):
            return 0.6
        return 0.0

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self.config.get("entity_id"):
            errors.append("entity_id is required")
        mapping = self.config.get("state_mapping")
        if mapping is not None and not isinstance(mapping, dict):
            errors.append("state_mapping must be a dict if provided")
        return errors
