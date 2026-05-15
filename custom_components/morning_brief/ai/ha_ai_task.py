"""Home Assistant `ai_task` provider.

Delegates the prompt to any user-configured `ai_task.*` entity (HA's
generic AI task abstraction). The wrapped entity decides which backend
to call (OpenAI Conversation, Google, Anthropic, local LLM, etc.) — we
just forward the rendered prompt and the model's response.

See MORNING_BRIEF_SPEC.md Section 13.3.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..const import AI_PROVIDER_HA_AI_TASK
from ..types import AIResult
from .base import AIProvider

_LOGGER = logging.getLogger(__name__)


class HAAITaskProvider(AIProvider):
    """Wraps an `ai_task.*` entity via the ai_task.generate_data service."""

    provider_type = AI_PROVIDER_HA_AI_TASK

    @property
    def entity_id(self) -> str:
        return str(self.config["entity_id"])

    async def generate(
        self, prompt: str, language: str, max_tokens: int = 2000
    ) -> AIResult:
        """Call `ai_task.generate_data` and unwrap the response.

        ``language`` and ``max_tokens`` are not passed through to the
        service — `ai_task` entities own their own model/parameter
        configuration. The prompt itself contains the language directive
        (D20).
        """
        start = time.monotonic()
        try:
            response: dict[str, Any] | None = await self.hass.services.async_call(
                "ai_task",
                "generate_data",
                {
                    "entity_id": self.entity_id,
                    "task_name": "Morning Brief",
                    "instructions": prompt,
                },
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 — wrap into AIResult per D9
            duration = int((time.monotonic() - start) * 1000)
            _LOGGER.warning("ai_task.generate_data failed: %s", err)
            return AIResult(
                status="error",
                content=None,
                error_message=str(err),
                tokens_used=None,
                duration_ms=duration,
            )

        duration = int((time.monotonic() - start) * 1000)
        if not response or "data" not in response:
            return AIResult(
                status="error",
                content=None,
                error_message="empty_response",
                tokens_used=None,
                duration_ms=duration,
            )
        return AIResult(
            status="ok",
            content=str(response["data"]),
            error_message=None,
            tokens_used=None,
            duration_ms=duration,
        )

    async def validate_credentials(self) -> bool:
        """The 'credential' is just an existing ai_task entity in HA."""
        return self.entity_id in self.hass.states.async_entity_ids("ai_task")
