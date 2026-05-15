"""Logical-day strategy registry + factory.

Three strategies (D6): fixed_cutoff (default), sleep_sensor, manual.
See MORNING_BRIEF_SPEC.md Section 7.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import (
    LOGICAL_DAY_FIXED_CUTOFF,
    LOGICAL_DAY_MANUAL,
    LOGICAL_DAY_SLEEP_SENSOR,
)
from ..exceptions import ConfigurationError
from .base import LogicalDayStrategy
from .fixed_cutoff import FixedCutoffStrategy
from .manual import ManualStrategy
from .sleep_sensor import SleepSensorStrategy

STRATEGIES: dict[str, type[LogicalDayStrategy]] = {
    LOGICAL_DAY_FIXED_CUTOFF: FixedCutoffStrategy,
    LOGICAL_DAY_SLEEP_SENSOR: SleepSensorStrategy,
    LOGICAL_DAY_MANUAL: ManualStrategy,
}


def create_strategy(
    hass: HomeAssistant, strategy_type: str, config: dict[str, Any]
) -> LogicalDayStrategy:
    """Instantiate the strategy for ``strategy_type`` and validate its config.

    Raises:
        ConfigurationError: unknown strategy or invalid config (R5).
    """
    if strategy_type not in STRATEGIES:
        raise ConfigurationError(f"Unknown logical_day strategy: {strategy_type}")
    cls = STRATEGIES[strategy_type]
    instance = cls(hass, config)
    errors = instance.validate_config()
    if errors:
        raise ConfigurationError(
            f"Invalid logical_day config for {strategy_type}: {errors}"
        )
    return instance


__all__ = [
    "STRATEGIES",
    "LogicalDayStrategy",
    "create_strategy",
]
