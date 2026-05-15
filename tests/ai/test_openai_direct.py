"""Tests for ai/openai_direct.py (Section 13.5)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.ai.openai_direct import OpenAIDirectProvider

CFG = {"api_key": "sk-test", "model": "gpt-4o-mini"}


def _mock_session(
    status: int = 200, payload: dict | None = None, body_text: str = ""
) -> MagicMock:
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


async def test_generate_success_unwraps_choices(hass: HomeAssistant) -> None:
    payload = {
        "choices": [{"message": {"content": '{"verdict": "ok"}'}}],
        "usage": {"completion_tokens": 17},
    }
    with patch(
        "custom_components.morning_brief.ai.openai_direct.aiohttp_client.async_get_clientsession",
        return_value=_mock_session(status=200, payload=payload),
    ):
        r = await OpenAIDirectProvider(hass, CFG).generate("prompt", "en")
    assert r.status == "ok"
    assert r.content == '{"verdict": "ok"}'
    assert r.tokens_used == 17


async def test_generate_non_200_is_error(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.morning_brief.ai.openai_direct.aiohttp_client.async_get_clientsession",
        return_value=_mock_session(status=429, body_text="rate limited"),
    ):
        r = await OpenAIDirectProvider(hass, CFG).generate("prompt", "en")
    assert r.status == "error"
    assert "http_429" in (r.error_message or "")


async def test_generate_exception_is_error(hass: HomeAssistant) -> None:
    session = MagicMock()
    session.post = MagicMock(side_effect=RuntimeError("ssl boom"))
    with patch(
        "custom_components.morning_brief.ai.openai_direct.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        r = await OpenAIDirectProvider(hass, CFG).generate("prompt", "en")
    assert r.status == "error"
