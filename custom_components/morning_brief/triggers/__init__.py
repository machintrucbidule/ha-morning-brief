"""Trigger registry.

Three coexisting trigger levels (D7): schedule (L1), sensor_based (L2),
external (L3 — service-only, no implementation here). See
MORNING_BRIEF_SPEC.md Section 16.
"""

from __future__ import annotations

from .schedule import ScheduleTrigger
from .sensor_based import SensorBasedTrigger

__all__ = [
    "ScheduleTrigger",
    "SensorBasedTrigger",
]
