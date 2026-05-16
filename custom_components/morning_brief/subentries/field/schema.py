"""Voluptuous schemas for the field subentry, per provider type (Section 21.2).

The flow handler (``flow.py``) picks the right schema once
``provider_type`` is known and presents the corresponding extra fields.

Every entity-pointing input uses ``selector.EntitySelector`` (G18) so the
user picks from a dropdown of HA entities, never a free-text field.
Every enum uses ``selector.SelectSelector`` with translation_key so the
options display as human-readable labels.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

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
            vol.Required(
                "entity_id", default=current.get("entity_id", "")
            ): selector.EntitySelector(selector.EntitySelectorConfig()),
            vol.Required(
                "provider_type",
                default=current.get("provider_type", PROVIDER_INSTANTANEOUS),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(PROVIDER_TYPES),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="provider_type",
                )
            ),
        }
    )


def provider_params_schema(
    provider_type: str, current: dict[str, Any]
) -> vol.Schema:
    """Step 2 — provider-specific params (the ``provider_config`` block).

    ``current`` includes the previously-picked ``entity_id`` (from step 1)
    so we can target ``AttributeSelector`` at the right entity when
    needed.
    """
    pc = dict(current.get("provider_config") or {})
    entity_id = str(current.get("entity_id") or "")

    if provider_type == PROVIDER_CUMULATIVE:
        return vol.Schema(
            {
                vol.Optional(
                    "reset_hour", default=int(pc.get("reset_hour", 0))
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
    if provider_type == PROVIDER_INSTANTANEOUS:
        return vol.Schema(
            {
                vol.Optional(
                    "aggregation", default=pc.get("aggregation", "mean")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["mean", "last"],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="instantaneous_aggregation",
                    )
                ),
                vol.Optional(
                    "window_hours_today",
                    default=int(pc.get("window_hours_today", 24)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=72, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
    if provider_type == PROVIDER_EVENT_BASED:
        return vol.Schema(
            {
                vol.Optional(
                    "epsilon", default=float(pc.get("epsilon", 0.0))
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, step=0.001, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    "min_debounce_minutes",
                    default=int(pc.get("min_debounce_minutes", 5)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=240, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
    if provider_type == PROVIDER_DURATION:
        # Choose how to measure the "since" timestamp:
        # - input_datetime → the entity IS the reference timestamp
        #   (point to an input_datetime.* entity directly).
        # - sensor_last_changed → use the sensor's last_changed metadata.
        # - sensor_attribute_datetime → read a datetime from a sensor attribute.
        attribute_selector: Any
        if entity_id:
            attribute_selector = selector.AttributeSelector(
                selector.AttributeSelectorConfig(entity_id=entity_id)
            )
        else:
            attribute_selector = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )
        return vol.Schema(
            {
                vol.Required(
                    "source_type",
                    default=pc.get("source_type", "input_datetime"),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            "input_datetime",
                            "sensor_last_changed",
                            "sensor_attribute_datetime",
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="duration_source_type",
                    )
                ),
                vol.Optional(
                    "attribute_name", default=pc.get("attribute_name", "")
                ): attribute_selector,
                vol.Optional(
                    "display_unit", default=pc.get("display_unit", "auto")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["auto", "days", "hours", "minutes"],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="duration_display_unit",
                    )
                ),
            }
        )
    if provider_type == PROVIDER_STATE:
        return vol.Schema(
            {
                vol.Optional(
                    "state_mapping_json", default=pc.get("state_mapping_json", "")
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT, multiline=True
                    )
                ),
            }
        )
    if provider_type == PROVIDER_CALENDAR:
        return vol.Schema(
            {
                vol.Optional(
                    "summary_regex", default=pc.get("summary_regex", "")
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Optional(
                    "window_days", default=int(pc.get("window_days", 7))
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=365, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    "max_events", default=int(pc.get("max_events", 1))
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=20, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
    if provider_type == PROVIDER_WEATHER:
        return vol.Schema(
            {
                vol.Optional(
                    "source_format",
                    default=pc.get("source_format", "ha_weather"),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["ha_weather", "structured_attributes"],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="weather_source_format",
                    )
                ),
            }
        )
    if provider_type == PROVIDER_MANUAL:
        return vol.Schema(
            {
                vol.Optional(
                    "value_type", default=pc.get("value_type", "number")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["number", "text", "datetime"],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="manual_value_type",
                    )
                ),
            }
        )
    return vol.Schema({})


def display_schema(
    current: dict[str, Any], categories: list[tuple[str, str]]
) -> vol.Schema:
    """Step 3 — label / icon / category_id / unit / direction_preference.

    ``categories`` is a list of (category_id, display_label) tuples so
    the user picks from human-readable names, not raw slugs.
    """
    if categories:
        options = [
            selector.SelectOptionDict(value=cid, label=label)
            for cid, label in categories
        ]
        default_cid = current.get("category_id", categories[0][0])
    else:
        options = [
            selector.SelectOptionDict(
                value="uncategorised", label="(no category yet — create one first)"
            )
        ]
        default_cid = "uncategorised"

    return vol.Schema(
        {
            vol.Required("label", default=current.get("label", "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "icon", default=current.get("icon", "")
            ): selector.IconSelector(),
            vol.Required(
                "category_id", default=default_cid
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                "unit", default=current.get("unit", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "direction_preference",
                default=current.get("direction_preference", DIRECTION_NEUTRAL),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(DIRECTION_PREFERENCES),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="direction_preference",
                )
            ),
        }
    )


def comparisons_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 4 — comparisons (which types + window_days + target)."""
    enabled = {c.get("type") for c in current.get("comparisons", _DEFAULT_COMPARISONS)}
    return vol.Schema(
        {
            vol.Optional(
                "enabled_comparisons", default=sorted(enabled)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(COMPARISON_TYPES),
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="comparison_type",
                )
            ),
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
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=3, max=90, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "target_value", default=float(current.get("target_value", 0.0))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    step=0.01, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


def anomaly_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 5 — anomaly detection mode + params + severity."""
    ad = current.get("anomaly_detection") or {}
    return vol.Schema(
        {
            vol.Optional(
                "mode", default=ad.get("mode", ANOMALY_NONE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(ANOMALY_MODES),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="anomaly_mode",
                )
            ),
            vol.Optional(
                "sigmas", default=float(ad.get("sigmas", 2.0))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.5, max=10, step=0.1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "window_days", default=int(ad.get("window_days", 14))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=3, max=90, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "min_value", default=str(ad.get("min_value") or "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "max_value", default=str(ad.get("max_value") or "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "pct", default=float(ad.get("pct", 0.0))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    step=0.1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "severity", default=ad.get("severity", ANOMALY_SEVERITY_WARNING)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(ANOMALY_SEVERITIES),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="anomaly_severity",
                )
            ),
        }
    )


def visibility_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 6 — visible_in + weekly_aggregation + AI policy."""
    return vol.Schema(
        {
            vol.Optional(
                "visible_in", default=current.get("visible_in", list(REPORT_TYPES))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(REPORT_TYPES),
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="report_type",
                )
            ),
            vol.Optional(
                "weekly_aggregation",
                default=current.get("weekly_aggregation", WEEKLY_AGG_MEAN),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(WEEKLY_AGGREGATIONS),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="weekly_aggregation",
                )
            ),
            vol.Optional(
                "ai_insight_policy",
                default=current.get("ai_insight_policy", "optional"),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["optional", "required", "forbidden"],
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="ai_insight_policy",
                )
            ),
        }
    )


def gate_schema(current: dict[str, Any]) -> vol.Schema:
    """Step 7 — optional availability gate (D5)."""
    gate = current.get("availability_gate") or {}
    return vol.Schema(
        {
            vol.Optional(
                "gate_entity_id", default=gate.get("entity_id", "")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(
                "gate_expected_state",
                default=gate.get("expected_state", "off"),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )
