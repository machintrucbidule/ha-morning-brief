"""AIProvider ABC.

Each concrete provider returns an :class:`AIResult` from
:meth:`generate`. The retry wrapper (``ai/retry.py``) calls
``generate`` up to N times with exponential back-off (D8) and
JSON-validates the response. ``validate_credentials`` is a runtime
health check the config flow can call.

See MORNING_BRIEF_SPEC.md Section 13.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from homeassistant.core import HomeAssistant

from ..types import AIResult

__all__ = ["AIProvider", "AIResult"]


class AIProvider(ABC):
    """Abstract base for every AI provider implementation (D8)."""

    provider_type: str  # set by each subclass to one of const.AI_PROVIDER_TYPES

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Bind to an HA instance and the per-instance config block."""
        self.hass = hass
        self.config = config

    @abstractmethod
    async def generate(
        self, prompt: str, language: str, max_tokens: int = 2000
    ) -> AIResult:
        """Send the rendered prompt to the backing model.

        ``language`` is the BCP-47 short code (e.g. ``fr`` / ``en``). The
        model is expected to reply in that language — see D20.
        """

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Quick credential check. May make a minimal API call."""
