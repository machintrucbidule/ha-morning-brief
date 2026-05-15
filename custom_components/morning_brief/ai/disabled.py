"""Disabled AI provider (degraded mode).

Per D9 the brief must still be generated when AI is unavailable. This
provider implements the "disabled" choice and returns a syntactically
valid, semantically empty JSON envelope so the report builder can splice
it in without special-casing. ``ai_status`` will be set to ``disabled``
by the report builder (Phase 7).
"""

from __future__ import annotations

import json
from typing import Final

from ..const import AI_PROVIDER_DISABLED
from ..types import AIResult
from .base import AIProvider

_EMPTY_ENVELOPE: Final = json.dumps(
    {
        "alertes_formulees": [],
        "insights": {},
        "weather_synthesis": "",
        "verdict": "",
    }
)


class DisabledProvider(AIProvider):
    """No-op provider. Always returns the empty JSON envelope."""

    provider_type = AI_PROVIDER_DISABLED

    async def generate(
        self, prompt: str, language: str, max_tokens: int = 2000
    ) -> AIResult:
        """Return the empty envelope; signal success so retry doesn't fire."""
        return AIResult(
            status="ok",
            content=_EMPTY_ENVELOPE,
            error_message=None,
            tokens_used=0,
            duration_ms=0,
        )

    async def validate_credentials(self) -> bool:
        """No credentials to validate."""
        return True
