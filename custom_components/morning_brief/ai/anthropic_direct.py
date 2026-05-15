"""Direct Anthropic Messages API provider.

User supplies an API key in ``config_entry.data`` (D22). HTTP I/O via
HA's shared aiohttp client session (R9). Per D9 every failure converts
to an :class:`AIResult` with ``status=error`` rather than raising.

See MORNING_BRIEF_SPEC.md Section 13.4.
"""

from __future__ import annotations

import logging
import time

import aiohttp
from homeassistant.helpers import aiohttp_client

from ..const import AI_PROVIDER_ANTHROPIC_DIRECT
from ..types import AIResult
from .base import AIProvider

_LOGGER = logging.getLogger(__name__)

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_DEFAULT_MODEL = "claude-sonnet-4-7"
_HTTP_TIMEOUT_SECONDS = 60


class AnthropicDirectProvider(AIProvider):
    """Direct calls to api.anthropic.com (no HA Conversation integration)."""

    provider_type = AI_PROVIDER_ANTHROPIC_DIRECT

    @property
    def api_key(self) -> str:
        return str(self.config["api_key"])

    @property
    def model(self) -> str:
        return str(self.config.get("model", _DEFAULT_MODEL))

    async def generate(
        self, prompt: str, language: str, max_tokens: int = 2000
    ) -> AIResult:
        """POST a single-message request to /v1/messages."""
        del language  # language is embedded in the prompt itself (D20)
        session = aiohttp_client.async_get_clientsession(self.hass)
        start = time.monotonic()
        try:
            async with session.post(
                _API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": _API_VERSION,
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
                content = data["content"][0]["text"]
                tokens = data.get("usage", {}).get("output_tokens")
                return AIResult(
                    status="ok",
                    content=str(content),
                    error_message=None,
                    tokens_used=int(tokens) if tokens is not None else None,
                    duration_ms=duration,
                )
        except Exception as err:  # noqa: BLE001 — D9: never let AI errors crash the brief
            duration = int((time.monotonic() - start) * 1000)
            _LOGGER.warning("Anthropic Messages API call failed: %s", err)
            return AIResult(
                status="error",
                content=None,
                error_message=str(err),
                tokens_used=None,
                duration_ms=duration,
            )

    async def validate_credentials(self) -> bool:
        """A small ping call. Returns False if the API key is rejected."""
        result = await self.generate("ping", language="en", max_tokens=10)
        return result.status == "ok"
