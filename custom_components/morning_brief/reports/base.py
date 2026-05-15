# rationale: bundles the ABC, the shared `ResolvedField` dataclass, the
# `_resolve_field` orchestration pipeline (provider → gate → comparisons
# → anomaly → sparkline) and the small formatting helpers. Splitting
# would scatter logic every concrete report needs.
"""ReportBuilder ABC and shared per-field resolution helpers.

Concrete builders (morning / evening / weekly) iterate the instance's
fields, call the compute layers (gate + comparisons + anomaly) and pack
the result through :func:`reports.canonical.build_canonical_json`.

The Phase-7 contract follows MORNING_BRIEF_SPEC.md Section 14.1 literally:
``ReportBuilder(hass, coordinator)``. The ``coordinator`` argument is
duck-typed — anything that exposes the attributes documented below
works, so tests can pass a ``SimpleNamespace`` while the real
coordinator (Phase 8+) populates them from config-flow state.

Expected ``coordinator`` attributes:
- ``entry_id: str``
- ``instance_name: str``
- ``language: str``  (one of const.SUPPORTED_LANGUAGES)
- ``fields: list[dict]``  (field configs — see Section 40)
- ``categories: list[dict]``  (category configs)
- ``logical_day_strategy: LogicalDayStrategy``
- ``ai_provider: AIProvider``
- ``prompt_template: PromptTemplate``
- ``previous_briefs_refs: list[str]``
- ``user_custom_context: str | None``
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from ..compute import apply_gate, detect_anomaly, evaluate_comparisons
from ..const import (
    HISTORY_AGG_CHANGE,
    HISTORY_AGG_LAST,
    HISTORY_AGG_MEAN,
    PROVIDER_CUMULATIVE,
    PROVIDER_DURATION,
    PROVIDER_EVENT_BASED,
    PROVIDER_INSTANTANEOUS,
    PROVIDER_MANUAL,
    PROVIDER_STATE,
)
from ..history import HistoryQuery, query
from ..providers import create_provider
from ..providers.base import FieldProvider
from ..types import AnomalyResult, AvailabilityGate, Comparison, FieldValue

SPARKLINE_DAYS = 7
_NUMERIC_PROVIDER_TO_SPARKLINE_AGG: dict[str, str] = {
    PROVIDER_CUMULATIVE: HISTORY_AGG_CHANGE,
    PROVIDER_INSTANTANEOUS: HISTORY_AGG_MEAN,
    PROVIDER_EVENT_BASED: HISTORY_AGG_LAST,
    PROVIDER_DURATION: HISTORY_AGG_LAST,
}
# Non-numeric providers (state / manual / calendar / weather) skip sparkline.
_NO_SPARKLINE_PROVIDERS = frozenset({PROVIDER_STATE, PROVIDER_MANUAL, "calendar", "weather"})


@dataclass
class ResolvedField:
    """Fully-resolved per-field data ready to drop into the canonical JSON."""

    id: str
    label: str
    icon: str
    order: int
    category_id: str
    provider_type: str
    direction_preference: str
    value: FieldValue
    comparisons: list[Comparison] = field(default_factory=list)
    anomaly: AnomalyResult | None = None
    sparkline_data: list[float] = field(default_factory=list)


def _format_value(value: float | int | str | None, unit: str | None) -> str:
    """Minimal numeric formatter — Phase 11 will localise this properly."""
    if value is None:
        return "—"
    text = f"{value:g}" if isinstance(value, int | float) else str(value)
    return f"{text} {unit}" if unit else text


def _format_delta(delta: float | None, unit: str | None) -> str:
    if delta is None:
        return ""
    sign = "+" if delta > 0 else ""
    text = f"{sign}{delta:g}"
    return f"{text} {unit}" if unit else text


def _annotate_comparisons(
    comparisons: list[Comparison], unit: str | None
) -> list[Comparison]:
    """Populate ``formatted`` / ``delta_formatted`` strings in-place."""
    for c in comparisons:
        c.formatted = _format_value(c.value, unit)
        c.delta_formatted = _format_delta(c.delta, unit)
    return comparisons


def _gate_for(field_config: dict[str, Any]) -> AvailabilityGate | None:
    raw = field_config.get("availability_gate")
    if not raw:
        return None
    return AvailabilityGate(
        entity_id=str(raw["entity_id"]),
        expected_state=str(raw["expected_state"]),
    )


async def _sparkline(
    hass: HomeAssistant,
    provider: FieldProvider,
    field_config: dict[str, Any],
    logical_date: date,
) -> list[float]:
    """Return ≤ ``SPARKLINE_DAYS`` numeric daily values ending at ``logical_date``."""
    provider_type = field_config.get("provider_type", "")
    if provider_type in _NO_SPARKLINE_PROVIDERS:
        return []
    agg = _NUMERIC_PROVIDER_TO_SPARKLINE_AGG.get(provider_type)
    if agg is None:
        return []
    entity_id = provider.config.get("entity_id")
    if not entity_id:
        return []
    start = logical_date - timedelta(days=SPARKLINE_DAYS - 1)
    try:
        result = await query(
            hass,
            HistoryQuery(
                entity_id=str(entity_id),
                start_date=start,
                end_date=logical_date,
                aggregation=agg,
            ),
        )
    except Exception:  # noqa: BLE001 — defensive at the orchestration boundary
        return []
    return [v for v in result.data.values() if v is not None]


async def _anomaly_for(
    hass: HomeAssistant,
    provider: FieldProvider,
    field_config: dict[str, Any],
    logical_date: date,
    current_value: FieldValue,
) -> AnomalyResult | None:
    """Run the per-field anomaly detector. None when no detection configured."""
    detect_cfg = field_config.get("anomaly_detection") or {}
    mode = detect_cfg.get("mode", "none")
    if mode == "none":
        return None
    raw = current_value.raw if isinstance(current_value.raw, int | float) else None
    history: list[float] = []
    if mode in {"z_score", "pct_change_vs_rolling_avg"}:
        window = int(detect_cfg.get("window_days", 14))
        entity_id = provider.config.get("entity_id")
        if entity_id:
            try:
                result = await query(
                    hass,
                    HistoryQuery(
                        entity_id=str(entity_id),
                        start_date=logical_date - timedelta(days=window),
                        end_date=logical_date - timedelta(days=1),
                        aggregation=HISTORY_AGG_MEAN,
                    ),
                )
                history = [v for v in result.data.values() if v is not None]
            except Exception:  # noqa: BLE001
                history = []
    return detect_anomaly(detect_cfg, current=raw, history=history)


class ReportBuilder(ABC):
    """Abstract base for every report type (D12)."""

    report_type: str

    def __init__(self, hass: HomeAssistant, coordinator: Any) -> None:
        """Bind to HA and to a duck-typed coordinator (see module docstring)."""
        self.hass = hass
        self.coordinator = coordinator

    @abstractmethod
    async def build(self, logical_date: date, cal_offset: int = 0) -> dict[str, Any]:
        """Produce the canonical JSON dict (Section 15)."""

    async def _resolve_field(
        self, field_config: dict[str, Any], logical_date: date
    ) -> ResolvedField:
        """Shared pipeline: provider → gate → comparisons → anomaly → sparkline."""
        provider = create_provider(
            self.hass,
            str(field_config["provider_type"]),
            dict(field_config.get("provider_config") or {}),
        )
        value = await provider.get_current_value(logical_date)
        value = await apply_gate(
            self.hass, value, _gate_for(field_config), logical_date, provider
        )
        direction_pref = str(field_config.get("direction_preference", "neutral"))
        unit = str(field_config.get("unit") or value.unit or "") or None
        comparisons = await evaluate_comparisons(
            self.hass,
            provider,
            value,
            logical_date,
            field_config,
            direction_pref,
        )
        _annotate_comparisons(comparisons, unit)
        anomaly = await _anomaly_for(
            self.hass, provider, field_config, logical_date, value
        )
        sparkline = await _sparkline(self.hass, provider, field_config, logical_date)
        return ResolvedField(
            id=str(field_config["field_id"]),
            label=str(field_config.get("label", "")),
            icon=str(field_config.get("icon", "")),
            order=int(field_config.get("order", 0)),
            category_id=str(field_config.get("category_id", "")),
            provider_type=str(field_config["provider_type"]),
            direction_preference=direction_pref,
            value=value,
            comparisons=comparisons,
            anomaly=anomaly,
            sparkline_data=sparkline,
        )
