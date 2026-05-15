"""Tests for logical_day/__init__.py — registry + factory (D6)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.morning_brief.const import (
    LOGICAL_DAY_FIXED_CUTOFF,
    LOGICAL_DAY_MANUAL,
    LOGICAL_DAY_SLEEP_SENSOR,
    LOGICAL_DAY_STRATEGIES,
)
from custom_components.morning_brief.exceptions import ConfigurationError
from custom_components.morning_brief.logical_day import (
    STRATEGIES,
    create_strategy,
)
from custom_components.morning_brief.logical_day.fixed_cutoff import (
    FixedCutoffStrategy,
)


def test_registry_covers_all_v1_strategies() -> None:
    assert set(STRATEGIES.keys()) == set(LOGICAL_DAY_STRATEGIES)


def test_create_strategy_happy_path(hass: HomeAssistant) -> None:
    s = create_strategy(hass, LOGICAL_DAY_FIXED_CUTOFF, {"cutoff_hour": 5})
    assert isinstance(s, FixedCutoffStrategy)


def test_create_strategy_unknown_type_raises(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError, match="Unknown"):
        create_strategy(hass, "blob", {})


def test_create_strategy_invalid_config_raises(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError, match="Invalid"):
        create_strategy(hass, LOGICAL_DAY_FIXED_CUTOFF, {"cutoff_hour": 99})


@pytest.mark.parametrize(
    ("stype", "config"),
    [
        (LOGICAL_DAY_FIXED_CUTOFF, {}),
        (LOGICAL_DAY_SLEEP_SENSOR, {"sleep_sensor_entity": "binary_sensor.x"}),
        (LOGICAL_DAY_MANUAL, {}),
    ],
)
def test_create_strategy_for_every_v1_type(
    hass: HomeAssistant, stype: str, config: dict
) -> None:
    s = create_strategy(hass, stype, config)
    assert s.strategy_type == stype
