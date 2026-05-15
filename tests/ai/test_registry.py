"""Tests for ai/__init__.py — registry + factory (D8)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.morning_brief.ai import AI_PROVIDERS, create_ai_provider
from custom_components.morning_brief.ai.disabled import DisabledProvider
from custom_components.morning_brief.const import AI_PROVIDER_TYPES
from custom_components.morning_brief.exceptions import ConfigurationError


def test_registry_covers_all_v1_ai_provider_types() -> None:
    assert set(AI_PROVIDERS.keys()) == set(AI_PROVIDER_TYPES)


def test_create_disabled_provider_needs_no_config(hass: HomeAssistant) -> None:
    prov = create_ai_provider(hass, "disabled", {})
    assert isinstance(prov, DisabledProvider)


def test_create_unknown_type_raises(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError, match="Unknown"):
        create_ai_provider(hass, "blob", {})


def test_create_ha_ai_task_requires_entity_id(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError, match="entity_id"):
        create_ai_provider(hass, "ha_ai_task", {})


def test_create_anthropic_requires_api_key(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError, match="api_key"):
        create_ai_provider(hass, "anthropic_direct", {})


def test_create_openai_requires_api_key(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError, match="api_key"):
        create_ai_provider(hass, "openai_direct", {})


@pytest.mark.parametrize(
    ("ptype", "config"),
    [
        ("ha_ai_task", {"entity_id": "ai_task.x"}),
        ("anthropic_direct", {"api_key": "sk-x"}),
        ("openai_direct", {"api_key": "sk-x"}),
        ("disabled", {}),
    ],
)
def test_create_happy_path_for_every_type(
    hass: HomeAssistant, ptype: str, config: dict
) -> None:
    prov = create_ai_provider(hass, ptype, config)
    assert prov.provider_type == ptype
