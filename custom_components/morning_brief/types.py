"""Typed dataclasses and TypedDicts for the morning_brief integration.

These types are the in-memory representation. The canonical JSON
schema lives in `MORNING_BRIEF_SPEC.md` Section 15; the dataclasses
below are kept aligned with that schema so they round-trip cleanly
through `dataclasses.asdict`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict


@dataclass
class FieldValue:
    """The current value of a field, as returned by a provider.

    `raw` holds the numeric / string / None payload depending on provider type.
    `stale` + `stale_reason` are set by the provider or by the availability gate
    (compute/availability.py) when the value is from an earlier day.
    """

    raw: float | int | str | None
    unit: str | None = None
    stale: bool = False
    stale_reason: str | None = None
    as_of: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AvailabilityGate:
    """Transverse gate attached to any provider (D5)."""

    entity_id: str
    expected_state: str


@dataclass
class Comparison:
    """One comparison result for a field (Section 11)."""

    type: str
    window_days: int | None = None
    value: float | None = None
    formatted: str = ""
    delta: float | None = None
    delta_formatted: str = ""
    direction: str = "flat"  # "up" | "down" | "flat"
    interpretation: str = "neutral"  # "improvement" | "worsening" | "neutral"
    status: str = "ok"  # see const.STATUS_*
    days_used: int | None = None


@dataclass
class AnomalyResult:
    """Outcome of running the anomaly detector on a field (Section 12)."""

    detected: bool
    severity: str  # "info" | "warning" | "critical"
    mode: str
    message_key: str = ""  # translation key resolved by the report builder
    message: str = ""  # resolved/translated message
    raw_value: float | None = None
    threshold: float | None = None


@dataclass
class AIResult:
    """Raw result of an AIProvider.generate call (Section 13)."""

    status: str  # "ok" | "error"
    content: str | None
    error_message: str | None = None
    tokens_used: int | None = None
    duration_ms: int | None = None


class BriefMeta(TypedDict):
    """`meta` block of the canonical JSON (Section 15)."""

    instance_id: str
    instance_name: str
    report_type: str
    language: str
    generated_at: str
    calendar_date: str
    logical_date: str
    logical_day_strategy: str
    logical_day_offset: int
    ai_status: str
    ai_provider: str | None
    ai_error: str | None
    duration_ms: int


class Alert(TypedDict):
    """One entry in the `alerts` array (Section 15)."""

    severity: str
    source: str  # "anomaly" | "battery" | "ha_health" | "custom"
    field_id: str | None
    message: str
    raw_value: float | None
    threshold: float | None


class CanonicalField(TypedDict, total=False):
    """One field entry inside a category in the canonical JSON."""

    id: str
    label: str
    icon: str
    order: int
    provider_type: str
    value: dict[str, Any]
    extra: dict[str, Any]
    comparisons: list[dict[str, Any]]
    anomaly: dict[str, Any] | None
    sparkline_data: list[float]
    direction_preference: str


class CanonicalCategory(TypedDict, total=False):
    """One category entry in the canonical JSON."""

    id: str
    label: str
    icon: str
    order: int
    display_when_empty: bool
    fields: list[CanonicalField]


class AIOutput(TypedDict):
    """`ai_output` block of the canonical JSON."""

    category_insights: dict[str, str]
    weather_synthesis: str
    verdict: str


class HAHealth(TypedDict):
    """`ha_health` block of the canonical JSON."""

    status: str
    alerts: list[dict[str, Any]]
    data: dict[str, float]


class CanonicalBrief(TypedDict, total=False):
    """The full canonical JSON envelope (Section 15)."""

    schema_version: int
    meta: BriefMeta
    alerts: list[Alert]
    categories: list[CanonicalCategory]
    ai_output: AIOutput
    ha_health: HAHealth
    previous_briefs_refs: list[str]


class StoredBrief(TypedDict):
    """One entry in the BriefStore (Section 17.2)."""

    uuid: str
    generated_at: str
    report_type: str
    logical_date: str
    canonical_json: CanonicalBrief
    rendered_markdown: str
    notification_short: str
