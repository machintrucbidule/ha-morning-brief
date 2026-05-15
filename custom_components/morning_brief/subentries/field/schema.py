"""Voluptuous schemas for the field subentry, per provider type (Section 21.2).

The flow handler (``flow.py``) picks the right schema once
``provider_type`` is known and presents the corresponding extra fields.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from ...const import (
    ANOMALY_MODES,
    ANOMALY_NONE,
    ANOMALY_SEVERITIES,
    ANOMALY_SEVERITY_WARNING,
    COMPARISON_ROLLING_AVG,
    COMPARISON_SAME_WEEKDAY_LAST_WEEK,
    COMPARISON_TYPES,
    COMPARISON_YESTERDAY,
    DIRECTION_NEUTRAL,
    DIRECTION_PREFERENCES,
    PROVIDER_CALENDAR,
    PROVIDER_CUMULATIVE,
    PROVIDER_DURATION,
    PROVIDER_EVENT_BASED,
    PROVIDER_INSTANTANEOUS,
    PROVIDER_MANUAL,
    PROVIDER_STATE,
    PROVIDER_TYPES,
    PROVIDER_WEATHER,
    REPORT_TYPES,
    WEEKLY_AGG_MEAN,
    WEEKLY_AGGREGATIONS,
)

_DEFAULT_COMPARISONS = [
    {"type": COMPARISON_YESTERDAY},
    {"type": COMPARISON_SAME_WEEKDAY_LAST_WEEK},
    {"type": COMPARISON_ROLLING_AVG, "window_days": 14},
]


def identity_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 1 — entity_id + provider_type."""
    return vol.Schema(
        {
            vol.Required("entity_id", default=current.get("entity_id", "")): str,
            vol.Required(
                "provider_type",
                default=current.get("provider_type", PROVIDER_INSTANTANEOUS),
            ): vol.In(list(PROVIDER_TYPES)),
        }
    )


def provider_params_schema(
    provider_type: str, current: dict[str, Any]
) -> vol.Schema:
    """Step 2 — provider-specific params (the ``provider_config`` block)."""
    pc = dict(current.get("provider_config") or {})
    if provider_type == PROVIDER_CUMULATIVE:
        return vol.Schema(
            {
                vol.Optional("reset_hour", default=pc.get("reset_hour", 0)): vol.All(
                    int, vol.Range(min=0, max=23)
                ),
            }
        )
    if provider_type == PROVIDER_INSTANTANEOUS:
        return vol.Schema(
            {
                vol.Optional("aggregation", default=pc.get("aggregation", "mean")): vol.In(
                    ["mean", "last"]
                ),
                vol.Optional(
                    "window_hours_today", default=pc.get("window_hours_today", 24)
                ): vol.All(int, vol.Range(min=1, max=72)),
            }
        )
    if provider_type == PROVIDER_EVENT_BASED:
        return vol.Schema(
            {
                vol.Optional("epsilon", default=float(pc.get("epsilon", 0.0))): vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                ),
                vol.Optional(
                    "min_debounce_minutes",
                    default=int(pc.get("min_debounce_minutes", 5)),
                ): vol.All(int, vol.Range(min=0)),
            }
        )
    if provider_type == PROVIDER_DURATION:
        return vol.Schema(
            {
                vol.Required(
                    "source_type",
                    default=pc.get("source_type", "input_datetime"),
                ): vol.In(
                    ["input_datetime", "sensor_last_changed", "sensor_attribute_datetime"]
                ),
                vol.Optional(
                    "attribute_name", default=pc.get("attribute_name", "")
                ): str,
                vol.Optional(
                    "display_unit", default=pc.get("display_unit", "auto")
                ): vol.In(["auto", "days", "hours", "minutes"]),
            }
        )
    if provider_type == PROVIDER_STATE:
        return vol.Schema(
            {vol.Optional("state_mapping_json", default=""): str}
        )
    if provider_type == PROVIDER_CALENDAR:
        return vol.Schema(
            {
                vol.Optional("summary_regex", default=pc.get("summary_regex", "")): str,
                vol.Optional("window_days", default=int(pc.get("window_days", 7))): vol.All(
                    int, vol.Range(min=1, max=365)
                ),
                vol.Optional("max_events", default=int(pc.get("max_events", 1))): vol.All(
                    int, vol.Range(min=1, max=20)
                ),
            }
        )
    if provider_type == PROVIDER_WEATHER:
        return vol.Schema(
            {vol.Optional("source_format", default=pc.get("source_format", "")): str}
        )
    if provider_type == PROVIDER_MANUAL:
        return vol.Schema(
            {
                vol.Optional("value_type", default=pc.get("value_type", "number")): vol.In(
                    ["number", "text", "datetime"]
                ),
            }
        )
    return vol.Schema({})


def display_schema(current: dict[str, Any], category_ids: list[str]) -> vol.Schema:
    """Step 3 — label / icon / category_id / unit / direction_preference."""
    choices = category_ids or ["uncategorised"]
    return vol.Schema(
        {
            vol.Required("label", default=current.get("label", "")): str,
            vol.Optional("icon", default=current.get("icon", "")): str,
            vol.Required(
                "category_id", default=current.get("category_id", choices[0])
            ): vol.In(choices),
            vol.Optional("unit", default=current.get("unit", "")): str,
            vol.Optional(
                "direction_preference",
                default=current.get("direction_preference", DIRECTION_NEUTRAL),
            ): vol.In(list(DIRECTION_PREFERENCES)),
        }
    )


def comparisons_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 4 — comparisons (which types + window_days + target)."""
    enabled = {c.get("type") for c in current.get("comparisons", _DEFAULT_COMPARISONS)}
    return vol.Schema(
        {
            vol.Optional(
                "enabled_comparisons", default=sorted(enabled)
            ): [vol.In(list(COMPARISON_TYPES))],
            vol.Optional(
                "rolling_window_days",
                default=int(
                    next(
                        (
                            c.get("window_days", 14)
                            for c in current.get("comparisons", [])
                            if c.get("type") == COMPARISON_ROLLING_AVG
                        ),
                        14,
                    )
                ),
            ): vol.All(int, vol.Range(min=3, max=90)),
            vol.Optional(
                "target_value", default=current.get("target_value", 0.0)
            ): vol.Coerce(float),
        }
    )


def anomaly_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 5 — anomaly detection mode + params + severity."""
    ad = current.get("anomaly_detection") or {}
    return vol.Schema(
        {
            vol.Optional("mode", default=ad.get("mode", ANOMALY_NONE)): vol.In(
                list(ANOMALY_MODES)
            ),
            vol.Optional("sigmas", default=float(ad.get("sigmas", 2.0))): vol.All(
                vol.Coerce(float), vol.Range(min=0.5, max=10)
            ),
            vol.Optional("window_days", default=int(ad.get("window_days", 14))): vol.All(
                int, vol.Range(min=3, max=90)
            ),
            vol.Optional("min_value", default=ad.get("min_value", "")): str,
            vol.Optional("max_value", default=ad.get("max_value", "")): str,
            vol.Optional("pct", default=float(ad.get("pct", 0.0))): vol.Coerce(float),
            vol.Optional(
                "severity", default=ad.get("severity", ANOMALY_SEVERITY_WARNING)
            ): vol.In(list(ANOMALY_SEVERITIES)),
        }
    )


def visibility_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 6 — visible_in + weekly_aggregation + AI policy."""
    return vol.Schema(
        {
            vol.Optional(
                "visible_in", default=current.get("visible_in", list(REPORT_TYPES))
            ): [vol.In(list(REPORT_TYPES))],
            vol.Optional(
                "weekly_aggregation",
                default=current.get("weekly_aggregation", WEEKLY_AGG_MEAN),
            ): vol.In(list(WEEKLY_AGGREGATIONS)),
            vol.Optional(
                "ai_insight_policy",
                default=current.get("ai_insight_policy", "optional"),
            ): vol.In(["optional", "required", "forbidden"]),
        }
    )


def gate_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 7 — optional availability gate (D5)."""
    gate = current.get("availability_gate") or {}
    return vol.Schema(
        {
            vol.Optional("gate_entity_id", default=gate.get("entity_id", "")): str,
            vol.Optional(
                "gate_expected_state", default=gate.get("expected_state", "off")
            ): str,
        }
    )
