"""Provider registry and factory.

The registry maps the closed V1 enum (D4) to concrete `FieldProvider`
subclasses. ``create_provider`` instantiates and validates one in a single
step (R5). ``detect_provider`` is the auto-detection helper used by the
config flow to suggest a default provider type for a chosen entity.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import (
    PROVIDER_CALENDAR,
    PROVIDER_CUMULATIVE,
    PROVIDER_DURATION,
    PROVIDER_EVENT_BASED,
    PROVIDER_INSTANTANEOUS,
    PROVIDER_MANUAL,
    PROVIDER_STATE,
    PROVIDER_WEATHER,
)
from ..exceptions import ConfigurationError
from .base import FieldProvider, FieldValue
from .calendar import CalendarProvider
from .cumulative import CumulativeProvider
from .duration import DurationProvider
from .event_based import EventBasedProvider
from .instantaneous import InstantaneousProvider
from .manual import ManualProvider
from .state import StateProvider
from .weather import WeatherProvider

PROVIDERS: dict[str, type[FieldProvider]] = {
    PROVIDER_CUMULATIVE: CumulativeProvider,
    PROVIDER_INSTANTANEOUS: InstantaneousProvider,
    PROVIDER_EVENT_BASED: EventBasedProvider,
    PROVIDER_STATE: StateProvider,
    PROVIDER_DURATION: DurationProvider,
    PROVIDER_CALENDAR: CalendarProvider,
    PROVIDER_WEATHER: WeatherProvider,
    PROVIDER_MANUAL: ManualProvider,
}


def create_provider(
    hass: HomeAssistant, provider_type: str, config: dict[str, Any]
) -> FieldProvider:
    """Instantiate the provider class for ``provider_type`` and validate config.

    Raises:
        ConfigurationError: if ``provider_type`` is unknown or the config
            fails validation per the provider's ``validate_config``.
    """
    if provider_type not in PROVIDERS:
        raise ConfigurationError(f"Unknown provider_type: {provider_type}")
    cls = PROVIDERS[provider_type]
    instance = cls(hass, config)
    errors = instance.validate_config()
    if errors:
        raise ConfigurationError(
            f"Invalid config for {provider_type}: {errors}"
        )
    return instance


def detect_provider(hass: HomeAssistant, entity_id: str) -> tuple[str, float]:
    """Return ``(provider_type, confidence)`` for the most likely provider.

    Defaults to ``("instantaneous", 0.0)`` when no provider claims the entity.
    """
    best: tuple[str, float] = (PROVIDER_INSTANTANEOUS, 0.0)
    for ptype, cls in PROVIDERS.items():
        score = cls.detect_from_entity(hass, entity_id)
        if score > best[1]:
            best = (ptype, score)
    return best


__all__ = [
    "PROVIDERS",
    "FieldProvider",
    "FieldValue",
    "create_provider",
    "detect_provider",
]
