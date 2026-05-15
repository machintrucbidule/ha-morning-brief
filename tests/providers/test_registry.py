"""Tests for providers/__init__.py — registry + factory (Section 8.9)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.morning_brief.const import (
    PROVIDER_CALENDAR,
    PROVIDER_CUMULATIVE,
    PROVIDER_DURATION,
    PROVIDER_EVENT_BASED,
    PROVIDER_INSTANTANEOUS,
    PROVIDER_MANUAL,
    PROVIDER_STATE,
    PROVIDER_TYPES,
    PROVIDER_WEATHER,
)
from custom_components.morning_brief.exceptions import ConfigurationError
from custom_components.morning_brief.providers import (
    PROVIDERS,
    create_provider,
    detect_provider,
)
from custom_components.morning_brief.providers.cumulative import CumulativeProvider
from custom_components.morning_brief.providers.instantaneous import (
    InstantaneousProvider,
)


def test_registry_covers_all_v1_provider_types() -> None:
    """The closed V1 enum (D4) must be 1:1 with the registry keys."""
    assert set(PROVIDERS.keys()) == set(PROVIDER_TYPES)


def test_create_provider_happy_path(hass: HomeAssistant) -> None:
    prov = create_provider(
        hass, PROVIDER_INSTANTANEOUS, {"entity_id": "sensor.x", "aggregation": "mean"}
    )
    assert isinstance(prov, InstantaneousProvider)


def test_create_provider_unknown_type_raises(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError, match="Unknown provider_type"):
        create_provider(hass, "blob", {})


def test_create_provider_invalid_config_raises(hass: HomeAssistant) -> None:
    """An empty config fails validation (entity_id required) → factory rejects."""
    with pytest.raises(ConfigurationError, match="Invalid config"):
        create_provider(hass, PROVIDER_INSTANTANEOUS, {})


def test_detect_provider_picks_highest_confidence(hass: HomeAssistant) -> None:
    """A total_increasing sensor scores 0.9 on cumulative, beats everything else."""
    eid = "sensor.daily_steps"
    hass.states.async_set(eid, "5000", {"state_class": "total_increasing"})
    ptype, score = detect_provider(hass, eid)
    assert ptype == PROVIDER_CUMULATIVE
    assert score == 0.9


def test_detect_provider_default_when_no_claim(hass: HomeAssistant) -> None:
    """Unknown entity → default fallback (instantaneous, 0.0)."""
    ptype, score = detect_provider(hass, "sensor.totally_unknown")
    assert ptype == PROVIDER_INSTANTANEOUS
    assert score == 0.0


def test_detect_provider_calendar_wins_for_calendar_entity(hass: HomeAssistant) -> None:
    ptype, score = detect_provider(hass, "calendar.personal")
    assert ptype == PROVIDER_CALENDAR
    assert score == 0.95


@pytest.mark.parametrize(
    ("ptype", "config"),
    [
        (PROVIDER_INSTANTANEOUS, {"entity_id": "sensor.x"}),
        (PROVIDER_CUMULATIVE, {"entity_id": "sensor.x"}),
        (PROVIDER_MANUAL, {"entity_id": "input_number.x"}),
        (PROVIDER_STATE, {"entity_id": "sensor.x"}),
        (PROVIDER_EVENT_BASED, {"entity_id": "sensor.x"}),
        (PROVIDER_DURATION, {"source_type": "input_datetime", "entity_id": "input_datetime.x"}),
        (PROVIDER_CALENDAR, {"calendar_entity_id": "calendar.x"}),
        (PROVIDER_WEATHER, {"source_entity_id": "weather.x"}),
    ],
)
def test_create_provider_for_every_v1_type(
    hass: HomeAssistant, ptype: str, config: dict
) -> None:
    prov = create_provider(hass, ptype, config)
    assert prov.provider_type == ptype


# Silence unused-import warning for CumulativeProvider used only in parametrize id reuse.
_ = CumulativeProvider
