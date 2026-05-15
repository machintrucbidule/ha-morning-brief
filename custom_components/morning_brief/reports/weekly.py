"""Weekly report builder (Section 14.4, D13, G15).

For each field flagged ``visible_in: weekly``, aggregate its daily LTS
values over the 7-day ISO week ending at ``logical_date`` using the
per-field ``weekly_aggregation`` (D13). The 7 daily values double as
the sparkline. Comparisons available at the field level are kept
(target_value, same_week_last_year). Per-day comparisons (yesterday,
J-7, rolling_*) are filtered out — they don't apply to an aggregate.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from ..const import (
    AI_STATUS_OK,
    COMPARISON_SAME_WEEK_LAST_YEAR,
    COMPARISON_TARGET_VALUE,
    HISTORY_AGG_MEAN,
    REPORT_TYPE_WEEKLY,
)
from ..history import HistoryQuery, query
from ..providers import create_provider
from ..types import FieldValue
from .base import ReportBuilder, ResolvedField, _annotate_comparisons
from .canonical import build_canonical_json
from .morning import _call_ai, _visible_for

_LOGGER = logging.getLogger(__name__)

_WeeklyReducer = Callable[[list[float]], float]
_WEEKLY_REDUCERS: dict[str, _WeeklyReducer] = {
    "sum": lambda vs: float(sum(vs)),
    "mean": lambda vs: sum(vs) / len(vs),
    "max": lambda vs: float(max(vs)),
    "min": lambda vs: float(min(vs)),
    "latest": lambda vs: vs[-1],
}
_DEFAULT_WEEKLY_AGG = "mean"


def _week_window(logical_date: date, start_day_of_week: int) -> tuple[date, date]:
    """Return the inclusive ``[start, end]`` of the ISO week ending at logical_date.

    ``start_day_of_week`` follows the ISO convention (0=Monday … 6=Sunday).
    """
    days_since_start = (logical_date.weekday() - start_day_of_week) % 7
    start = logical_date - timedelta(days=days_since_start)
    end = start + timedelta(days=6)
    return start, end


def _aggregate(values: list[float], aggregation: str) -> float | None:
    reducer = _WEEKLY_REDUCERS.get(aggregation) or _WEEKLY_REDUCERS[_DEFAULT_WEEKLY_AGG]
    if not values:
        return None
    return reducer(values)


class WeeklyReport(ReportBuilder):
    """Weekly aggregate brief."""

    report_type = REPORT_TYPE_WEEKLY

    async def build(self, logical_date: date, cal_offset: int = 0) -> dict[str, Any]:
        """Build the canonical weekly JSON for the ISO week ending at ``logical_date``."""
        start_ts = time.monotonic()
        coordinator = self.coordinator
        start_day = int(getattr(coordinator, "weekly_start_day_of_week", 0))
        week_start, week_end = _week_window(logical_date, start_day)

        fields = _visible_for(
            list(getattr(coordinator, "fields", []) or []), self.report_type
        )
        resolved: list[ResolvedField] = []
        for field_config in fields:
            try:
                rf = await self._resolve_weekly(field_config, week_start, week_end, logical_date)
            except Exception:  # noqa: BLE001 — never let one bad field crash the brief
                _LOGGER.exception(
                    "Weekly field %s failed to resolve — skipped",
                    field_config.get("field_id"),
                )
                continue
            resolved.append(rf)

        prompt = await self._render_prompt(coordinator, resolved, logical_date)
        ai_envelope, ai_status, ai_error = await _call_ai(
            coordinator, prompt, language=str(getattr(coordinator, "language", "en"))
        )

        provider = getattr(coordinator, "ai_provider", None)
        return build_canonical_json(
            instance_id=str(getattr(coordinator, "entry_id", "")),
            instance_name=str(getattr(coordinator, "instance_name", "")),
            report_type=self.report_type,
            language=str(getattr(coordinator, "language", "en")),
            logical_date=logical_date,
            cal_offset=cal_offset,
            logical_day_strategy=str(
                getattr(
                    getattr(coordinator, "logical_day_strategy", None),
                    "strategy_type",
                    "",
                )
            ),
            fields_resolved=resolved,
            categories=list(getattr(coordinator, "categories", []) or []),
            ai_envelope=ai_envelope,
            ai_provider=provider.provider_type if provider else None,
            ai_status=ai_status if ai_envelope is not None else ai_status,
            ai_error=ai_error,
            previous_briefs_refs=list(
                getattr(coordinator, "previous_briefs_refs", []) or []
            ),
            duration_ms=int((time.monotonic() - start_ts) * 1000),
        )

    async def _resolve_weekly(
        self,
        field_config: dict[str, Any],
        week_start: date,
        week_end: date,
        logical_date: date,
    ) -> ResolvedField:
        provider = create_provider(
            self.hass,
            str(field_config["provider_type"]),
            dict(field_config.get("provider_config") or {}),
        )
        entity_id = provider.config.get("entity_id")
        aggregation = str(field_config.get("weekly_aggregation", _DEFAULT_WEEKLY_AGG))
        history_agg = (
            "change" if field_config.get("provider_type") == "cumulative" else HISTORY_AGG_MEAN
        )
        daily_values: list[float] = []
        if entity_id:
            try:
                result = await query(
                    self.hass,
                    HistoryQuery(
                        entity_id=str(entity_id),
                        start_date=week_start,
                        end_date=week_end,
                        aggregation=history_agg,
                    ),
                )
                daily_values = [v for v in result.data.values() if v is not None]
            except Exception:  # noqa: BLE001
                daily_values = []

        aggregated = _aggregate(daily_values, aggregation)
        unit = str(field_config.get("unit") or "") or None
        weekly_value = FieldValue(
            raw=aggregated,
            unit=unit,
            stale=aggregated is None,
            stale_reason="no_data_for_date" if aggregated is None else None,
        )
        # Build the limited comparison set for weekly: only target_value &
        # same_week_last_year per Section 14.4 spirit.
        filtered_field = dict(field_config)
        filtered_field["comparisons"] = [
            c
            for c in field_config.get("comparisons", [])
            if c.get("type") in {COMPARISON_TARGET_VALUE, COMPARISON_SAME_WEEK_LAST_YEAR}
        ]
        from ..compute import evaluate_comparisons  # local import — small surface

        comparisons = await evaluate_comparisons(
            self.hass,
            provider,
            weekly_value,
            logical_date,
            filtered_field,
            str(field_config.get("direction_preference", "neutral")),
        )
        _annotate_comparisons(comparisons, unit)
        return ResolvedField(
            id=str(field_config["field_id"]),
            label=str(field_config.get("label", "")),
            icon=str(field_config.get("icon", "")),
            order=int(field_config.get("order", 0)),
            category_id=str(field_config.get("category_id", "")),
            provider_type=str(field_config["provider_type"]),
            direction_preference=str(
                field_config.get("direction_preference", "neutral")
            ),
            value=weekly_value,
            comparisons=comparisons,
            anomaly=None,  # weekly anomaly detection not in V1 scope
            sparkline_data=daily_values,
        )

    async def _render_prompt(
        self, coordinator: Any, resolved: list[ResolvedField], logical_date: date
    ) -> str:
        template = getattr(coordinator, "prompt_template", None)
        if template is None:
            return ""
        language = str(getattr(coordinator, "language", "en"))
        partial = build_canonical_json(
            instance_id=str(getattr(coordinator, "entry_id", "")),
            instance_name=str(getattr(coordinator, "instance_name", "")),
            report_type=self.report_type,
            language=language,
            logical_date=logical_date,
            cal_offset=0,
            logical_day_strategy=str(
                getattr(
                    getattr(coordinator, "logical_day_strategy", None),
                    "strategy_type",
                    "",
                )
            ),
            fields_resolved=resolved,
            categories=list(getattr(coordinator, "categories", []) or []),
            ai_envelope=None,
            ai_provider=None,
            ai_status=AI_STATUS_OK,
        )
        return template.render(
            language=language,
            data=partial,
            data_json=json.dumps(partial, default=str, ensure_ascii=False),
            user_custom_context=getattr(coordinator, "user_custom_context", None),
            previous_briefs_json=json.dumps(
                getattr(coordinator, "previous_briefs", []) or [],
                default=str,
                ensure_ascii=False,
            ),
        )
