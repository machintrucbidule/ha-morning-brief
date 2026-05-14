"""Custom exception hierarchy for the morning_brief integration.

These are internal exception types (never shown to users — R1). User-facing
error copy goes through `translations/<lang>.json` under `exceptions.*`.
"""

from __future__ import annotations


class MorningBriefError(Exception):
    """Base class for all morning_brief errors."""


class ConfigurationError(MorningBriefError):
    """Raised when a config or subentry config is invalid."""


class HistoryError(MorningBriefError):
    """Raised when the history layer cannot serve a request.

    Examples: an entity has no LTS at all, or the recorder is unavailable.
    Callers should catch this and degrade gracefully (R8).
    """


class ProviderError(MorningBriefError):
    """Raised when a field provider fails to compute a value."""


class AIProviderError(MorningBriefError):
    """Raised by an AIProvider. Callers should fall through to degraded mode (D9)."""


class StoreError(MorningBriefError):
    """Raised when the BriefStore cannot read or write."""


class TriggerError(MorningBriefError):
    """Raised when a trigger cannot be registered or fired correctly."""
