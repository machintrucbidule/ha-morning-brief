"""Availability gate (Section 9, D5, G5).

The gate is a transverse, provider-agnostic mechanism that runs AFTER a
provider returns its value. When the gate sensor is not in the expected
state — or itself unavailable — the gate substitutes the previous valid
day's value and stamps a ``stale_reason``. Providers know nothing about
the gate (G5).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, timedelta

from homeassistant.core import HomeAssistant

from ..const import STALE_AWAITING_AVAILABILITY, STALE_GATE_SENSOR_UNAVAILABLE
from ..providers.base import FieldProvider
from ..types import AvailabilityGate, FieldValue

_LOGGER = logging.getLogger(__name__)


async def apply_gate(
    hass: HomeAssistant,
    field_value: FieldValue,
    gate: AvailabilityGate | None,
    logical_date: date,
    provider: FieldProvider,
) -> FieldValue:
    """Return ``field_value`` unchanged, or the previous valid day's value.

    The fallback FieldValue keeps the previous day's ``raw`` / ``unit`` /
    ``extra`` / ``as_of`` but is marked ``stale=True`` with one of:
    - ``awaiting_availability`` when the gate sensor reports a state other
      than ``expected_state`` (e.g. user still asleep so sleep_total isn't
      finalised).
    - ``gate_sensor_unavailable`` when the gate sensor itself is missing
      or in ``unavailable`` / ``unknown`` state — defensively conservative.

    If ``gate`` is None, returns ``field_value`` unchanged.
    """
    if gate is None:
        return field_value

    state = hass.states.get(gate.entity_id)
    if state is None or state.state in ("unavailable", "unknown"):
        return await _previous_day_fallback(
            provider, logical_date, STALE_GATE_SENSOR_UNAVAILABLE
        )

    if state.state != gate.expected_state:
        return await _previous_day_fallback(
            provider, logical_date, STALE_AWAITING_AVAILABILITY
        )

    return field_value


async def _previous_day_fallback(
    provider: FieldProvider, logical_date: date, stale_reason: str
) -> FieldValue:
    """Fetch the previous calendar day's value and tag it stale."""
    previous = await provider.get_value_for_date(logical_date - timedelta(days=1))
    return replace(previous, stale=True, stale_reason=stale_reason)
