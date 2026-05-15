"""Asynchronous retry wrapper for AI providers (D8 + G14).

Calls :meth:`AIProvider.generate` up to ``max_attempts`` times with
exponential back-off (``base_delay`` × 2ⁿ seconds). On a successful
response with valid JSON, returns immediately. The back-off is pure
``asyncio.sleep`` so the coordinator can keep doing other work while
the retries are in flight.
"""

from __future__ import annotations

import asyncio
import json
import logging

from ..const import AI_RETRY_BASE_DELAY_SECONDS, AI_RETRY_MAX_ATTEMPTS
from ..types import AIResult
from .base import AIProvider

_LOGGER = logging.getLogger(__name__)


def _is_valid_json(text: str | None) -> bool:
    if not text:
        return False
    try:
        json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False
    return True


async def generate_with_retry(
    provider: AIProvider,
    prompt: str,
    language: str,
    max_attempts: int = AI_RETRY_MAX_ATTEMPTS,
    base_delay_seconds: int = AI_RETRY_BASE_DELAY_SECONDS,
) -> AIResult:
    """Wrap ``provider.generate`` with retries + JSON validation.

    A response counts as "successful" iff ``status == "ok"`` AND
    ``content`` parses as JSON. Anything else triggers a retry until
    ``max_attempts`` is exhausted; the final non-passing result is then
    returned so callers can inspect ``status`` / ``error_message``.

    Returns:
        The first passing ``AIResult``, or the last failure if all
        attempts fail. Never raises.
    """
    last: AIResult | None = None
    for attempt in range(max_attempts):
        result = await provider.generate(prompt, language)
        if result.status == "ok" and _is_valid_json(result.content):
            return result
        if result.status == "ok":
            _LOGGER.warning(
                "AI provider %s returned invalid JSON on attempt %d",
                provider.provider_type,
                attempt + 1,
            )
        last = result
        if attempt < max_attempts - 1:
            delay = base_delay_seconds * (2**attempt)
            _LOGGER.info(
                "AI provider %s retrying in %ds (attempt %d of %d)",
                provider.provider_type,
                delay,
                attempt + 2,
                max_attempts,
            )
            await asyncio.sleep(delay)
    # max_attempts == 0 is a misconfiguration; surface a synthetic error.
    if last is None:
        return AIResult(
            status="error",
            content=None,
            error_message="zero_attempts_configured",
            tokens_used=None,
            duration_ms=0,
        )
    return last
