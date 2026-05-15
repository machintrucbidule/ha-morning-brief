"""AI provider registry + factory + retry wrapper + prompt loader.

Four V1 providers (D8): ha_ai_task, anthropic_direct, openai_direct,
disabled. See MORNING_BRIEF_SPEC.md Section 13.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import (
    AI_PROVIDER_ANTHROPIC_DIRECT,
    AI_PROVIDER_DISABLED,
    AI_PROVIDER_HA_AI_TASK,
    AI_PROVIDER_OPENAI_DIRECT,
)
from ..exceptions import ConfigurationError
from .anthropic_direct import AnthropicDirectProvider
from .base import AIProvider, AIResult
from .disabled import DisabledProvider
from .ha_ai_task import HAAITaskProvider
from .openai_direct import OpenAIDirectProvider
from .prompt_template import PromptTemplate
from .retry import generate_with_retry

AI_PROVIDERS: dict[str, type[AIProvider]] = {
    AI_PROVIDER_HA_AI_TASK: HAAITaskProvider,
    AI_PROVIDER_ANTHROPIC_DIRECT: AnthropicDirectProvider,
    AI_PROVIDER_OPENAI_DIRECT: OpenAIDirectProvider,
    AI_PROVIDER_DISABLED: DisabledProvider,
}


def create_ai_provider(
    hass: HomeAssistant, provider_type: str, config: dict[str, Any]
) -> AIProvider:
    """Instantiate the AI provider class for ``provider_type``.

    Raises:
        ConfigurationError: for unknown provider_type or missing required
            config keys (api_key for the direct providers, entity_id for
            ha_ai_task).
    """
    if provider_type not in AI_PROVIDERS:
        raise ConfigurationError(f"Unknown AI provider_type: {provider_type}")
    cls = AI_PROVIDERS[provider_type]
    _validate_required(provider_type, config)
    return cls(hass, config)


def _validate_required(provider_type: str, config: dict[str, Any]) -> None:
    if provider_type == AI_PROVIDER_HA_AI_TASK and not config.get("entity_id"):
        raise ConfigurationError("ha_ai_task requires entity_id")
    if (
        provider_type in (AI_PROVIDER_ANTHROPIC_DIRECT, AI_PROVIDER_OPENAI_DIRECT)
        and not config.get("api_key")
    ):
        raise ConfigurationError(f"{provider_type} requires api_key")


__all__ = [
    "AI_PROVIDERS",
    "AIProvider",
    "AIResult",
    "PromptTemplate",
    "create_ai_provider",
    "generate_with_retry",
]
