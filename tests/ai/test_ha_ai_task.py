"""Tests for ai/ha_ai_task.py (Section 13.3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant, ServiceRegistry

from custom_components.morning_brief.ai.ha_ai_task import HAAITaskProvider

CFG = {"entity_id": "ai_task.local_llm"}


async def test_generate_success_returns_data_field(hass: HomeAssistant) -> None:
    with patch.object(
        ServiceRegistry,
        "async_call",
        AsyncMock(return_value={"data": '{"verdict": "ok"}'}),
    ):
        result = await HAAITaskProvider(hass, CFG).generate("the prompt", "fr")
    assert result.status == "ok"
    assert result.content == '{"verdict": "ok"}'
    assert result.duration_ms is not None


async def test_generate_missing_data_field_is_error(hass: HomeAssistant) -> None:
    with patch.object(
        ServiceRegistry, "async_call", AsyncMock(return_value={"other": "x"})
    ):
        result = await HAAITaskProvider(hass, CFG).generate("the prompt", "en")
    assert result.status == "error"
    assert result.error_message == "empty_response"


async def test_generate_empty_response_is_error(hass: HomeAssistant) -> None:
    with patch.object(ServiceRegistry, "async_call", AsyncMock(return_value=None)):
        result = await HAAITaskProvider(hass, CFG).generate("the prompt", "en")
    assert result.status == "error"


async def test_generate_service_failure_converts_to_error_result(
    hass: HomeAssistant,
) -> None:
    """Exceptions from the ai_task service become AIResult(status=error) per D9."""
    with patch.object(
        ServiceRegistry,
        "async_call",
        AsyncMock(side_effect=RuntimeError("ai_task boom")),
    ):
        result = await HAAITaskProvider(hass, CFG).generate("the prompt", "en")
    assert result.status == "error"
    assert "boom" in (result.error_message or "")


async def test_validate_credentials_true_when_entity_exists(hass: HomeAssistant) -> None:
    hass.states.async_set("ai_task.local_llm", "idle")
    assert await HAAITaskProvider(hass, CFG).validate_credentials() is True


async def test_validate_credentials_false_when_entity_missing(
    hass: HomeAssistant,
) -> None:
    assert await HAAITaskProvider(hass, CFG).validate_credentials() is False
