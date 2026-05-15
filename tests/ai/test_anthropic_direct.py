"""Tests for ai/anthropic_direct.py (Section 13.4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.ai.anthropic_direct import (
    AnthropicDirectProvider,
)

CFG = {"api_key": "sk-test", "model": "claude-sonnet-4-7"}


def _mock_session(
    status: int = 200, payload: dict | None = None, body_text: str = ""
) -> MagicMock:
    """Build a mock aiohttp session whose .post() returns an async-context-manager."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=payload or {})
    response.text = AsyncMock(return_value=body_text)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.post = MagicMock(return_value=ctx)
    return session


async def test_generate_success_returns_text(hass: HomeAssistant) -> None:
    payload = {
        "content": [{"type": "text", "text": '{"verdict": "ok"}'}],
        "usage": {"output_tokens": 42},
    }
    with patch(
        "custom_components.morning_brief.ai.anthropic_direct.aiohttp_client.async_get_clientsession",
        return_value=_mock_session(status=200, payload=payload),
    ):
        r = await AnthropicDirectProvider(hass, CFG).generate("prompt", "fr")
    assert r.status == "ok"
    assert r.content == '{"verdict": "ok"}'
    assert r.tokens_used == 42


async def test_generate_non_200_is_error(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.morning_brief.ai.anthropic_direct.aiohttp_client.async_get_clientsession",
        return_value=_mock_session(status=401, body_text="unauthorized"),
    ):
        r = await AnthropicDirectProvider(hass, CFG).generate("prompt", "en")
    assert r.status == "error"
    assert "http_401" in (r.error_message or "")


async def test_generate_network_exception_is_error(hass: HomeAssistant) -> None:
    """A connection / timeout error becomes AIResult(status=error) per D9."""
    session = MagicMock()
    session.post = MagicMock(side_effect=RuntimeError("dns failure"))
    with patch(
        "custom_components.morning_brief.ai.anthropic_direct.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        r = await AnthropicDirectProvider(hass, CFG).generate("prompt", "en")
    assert r.status == "error"
    assert "dns failure" in (r.error_message or "")
