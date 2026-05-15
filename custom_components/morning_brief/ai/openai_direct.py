"""Direct OpenAI Chat Completions API provider.

Mirrors the Anthropic provider's shape — same R9 aiohttp pattern, same
D9 error-to-AIResult conversion. The endpoint and message shape differ.

See MORNING_BRIEF_SPEC.md Section 13.5.
"""

from __future__ import annotations

import logging
import time

import aiohttp
from homeassistant.helpers import aiohttp_client

from ..const import AI_PROVIDER_OPENAI_DIRECT
from ..types import AIResult
from .base import AIProvider

_LOGGER = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_HTTP_TIMEOUT_SECONDS = 60


class OpenAIDirectProvider(AIProvider):
    """Direct calls to api.openai.com (no HA Conversation integration)."""

    provider_type = AI_PROVIDER_OPENAI_DIRECT

    @property
    def api_key(self) -> str:
        return str(self.config["api_key"])

    @property
    def model(self) -> str:
        return str(self.config.get("model", _DEFAULT_MODEL))

    async def generate(
        self, prompt: str, language: str, max_tokens: int = 2000
    ) -> AIResult:
        """POST a chat completion request."""
        del language
        session = aiohttp_client.async_get_clientsession(self.hass)
        start = time.monotonic()
        try:
            async with session.post(
                _API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=aiohttp.ClientTimeout(total=_HTTP_TIMEOUT_SECONDS),
            ) as resp:
                duration = int((time.monotonic() - start) * 1000)
                if resp.status != 200:
                    body = await resp.text()
                    return AIResult(
                        status="error",
                        content=None,
                        error_message=f"http_{resp.status}: {body[:200]}",
                        tokens_used=None,
                        duration_ms=duration,
                    )
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("completion_tokens")
                return AIResult(
                    status="ok",
                    content=str(content),
                    error_message=None,
                    tokens_used=int(tokens) if tokens is not None else None,
                    duration_ms=duration,
                )
        except Exception as err:  # noqa: BLE001 — D9
            duration = int((time.monotonic() - start) * 1000)
            _LOGGER.warning("OpenAI Chat Completions API call failed: %s", err)
            return AIResult(
                status="error",
                content=None,
                error_message=str(err),
                tokens_used=None,
                duration_ms=duration,
            )

    async def validate_credentials(self) -> bool:
        result = await self.generate("ping", language="en", max_tokens=10)
        return result.status == "ok"
