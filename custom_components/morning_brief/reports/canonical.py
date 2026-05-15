"""Canonical JSON builder (Section 14.5 + 15, D17).

Pure data assembly: given the meta info, the per-field resolution
output, the AI envelope, and a few optional blocks, return the dict
that mirrors Section 15 byte-for-byte. The card / renderings consume
this dict directly (D17).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any

from ..const import (
    AI_STATUS_OK,
    CANONICAL_SCHEMA_VERSION,
)
from ..types import AnomalyResult, FieldValue
from .base import ResolvedField, _format_value


def _field_value_to_dict(
    fv: FieldValue, unit: str | None
) -> dict[str, Any]:
    return {
        "raw": fv.raw,
        "formatted": _format_value(fv.raw, unit),
        "unit": unit,
        "stale": fv.stale,
        "stale_reason": fv.stale_reason,
        "as_of": fv.as_of.isoformat() if isinstance(fv.as_of, datetime) else None,
    }


def _anomaly_to_dict(anomaly: AnomalyResult | None) -> dict[str, Any] | None:
    if anomaly is None or not anomaly.detected:
        return None
    return asdict(anomaly)


def _resolved_field_to_dict(rf: ResolvedField) -> dict[str, Any]:
    unit = rf.value.unit
    return {
        "id": rf.id,
        "label": rf.label,
        "icon": rf.icon,
        "order": rf.order,
        "provider_type": rf.provider_type,
        "value": _field_value_to_dict(rf.value, unit),
        "extra": dict(rf.value.extra or {}),
        "comparisons": [asdict(c) for c in rf.comparisons],
        "anomaly": _anomaly_to_dict(rf.anomaly),
        "sparkline_data": list(rf.sparkline_data),
        "direction_preference": rf.direction_preference,
    }


def _group_fields_by_category(
    fields_resolved: list[ResolvedField],
    categories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the canonical ``categories`` list, sorted by order."""
    by_cat: dict[str, list[ResolvedField]] = {}
    for rf in fields_resolved:
        by_cat.setdefault(rf.category_id, []).append(rf)

    out: list[dict[str, Any]] = []
    for cat in sorted(categories, key=lambda c: int(c.get("order", 0))):
        cat_fields = sorted(
            by_cat.get(str(cat.get("id", "")), []), key=lambda r: r.order
        )
        display_when_empty = bool(cat.get("display_when_empty", False))
        if not cat_fields and not display_when_empty:
            continue
        out.append(
            {
                "id": str(cat.get("id", "")),
                "label": str(cat.get("label", "")),
                "icon": str(cat.get("icon", "")),
                "order": int(cat.get("order", 0)),
                "display_when_empty": display_when_empty,
                "fields": [_resolved_field_to_dict(rf) for rf in cat_fields],
            }
        )
    return out


def _anomaly_alerts(fields_resolved: list[ResolvedField]) -> list[dict[str, Any]]:
    """Synthesise canonical-shape alerts from detected anomalies."""
    alerts: list[dict[str, Any]] = []
    for rf in fields_resolved:
        if rf.anomaly is None or not rf.anomaly.detected:
            continue
        alerts.append(
            {
                "severity": rf.anomaly.severity,
                "source": "anomaly",
                "field_id": rf.id,
                "message": rf.anomaly.message or rf.anomaly.message_key,
                "raw_value": rf.anomaly.raw_value,
                "threshold": rf.anomaly.threshold,
            }
        )
    return alerts


def _meta(
    instance_id: str,
    instance_name: str,
    report_type: str,
    language: str,
    logical_date: date,
    cal_offset: int,
    logical_day_strategy: str,
    ai_status: str,
    ai_provider: str | None,
    ai_error: str | None,
    duration_ms: int,
) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    return {
        "instance_id": instance_id,
        "instance_name": instance_name,
        "report_type": report_type,
        "language": language,
        "generated_at": now.isoformat(),
        "calendar_date": now.astimezone().date().isoformat(),
        "logical_date": logical_date.isoformat(),
        "logical_day_strategy": logical_day_strategy,
        "logical_day_offset": cal_offset,
        "ai_status": ai_status,
        "ai_provider": ai_provider,
        "ai_error": ai_error,
        "duration_ms": duration_ms,
    }


def build_canonical_json(
    *,
    instance_id: str,
    instance_name: str,
    report_type: str,
    language: str,
    logical_date: date,
    cal_offset: int,
    logical_day_strategy: str,
    fields_resolved: list[ResolvedField],
    categories: list[dict[str, Any]],
    ai_envelope: dict[str, Any] | None,
    ai_provider: str | None,
    ai_status: str = AI_STATUS_OK,
    ai_error: str | None = None,
    ha_health: dict[str, Any] | None = None,
    previous_briefs_refs: list[str] | None = None,
    duration_ms: int = 0,
) -> dict[str, Any]:
    """Assemble the Section-15 dict in one place.

    ``ai_envelope`` is the parsed JSON the AI provider returned (or the
    empty envelope from the disabled provider). It contributes
    additional alerts (``alertes_formulees``) plus the
    ``ai_output`` block.
    """
    envelope = dict(ai_envelope or {})
    ai_output = {
        "category_insights": dict(envelope.get("insights") or {}),
        "weather_synthesis": str(envelope.get("weather_synthesis") or ""),
        "verdict": str(envelope.get("verdict") or ""),
    }
    canonical: dict[str, Any] = {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "meta": _meta(
            instance_id=instance_id,
            instance_name=instance_name,
            report_type=report_type,
            language=language,
            logical_date=logical_date,
            cal_offset=cal_offset,
            logical_day_strategy=logical_day_strategy,
            ai_status=ai_status,
            ai_provider=ai_provider,
            ai_error=ai_error,
            duration_ms=duration_ms,
        ),
        "alerts": [
            *_anomaly_alerts(fields_resolved),
            *_ai_alerts(envelope.get("alertes_formulees")),
        ],
        "categories": _group_fields_by_category(fields_resolved, categories),
        "ai_output": ai_output,
        "ha_health": dict(ha_health or {"status": "ok", "alerts": [], "data": {}}),
        "previous_briefs_refs": list(previous_briefs_refs or []),
    }
    return canonical


def _ai_alerts(raw: Any) -> list[dict[str, Any]]:
    """Convert the AI envelope's `alertes_formulees` list to canonical shape."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        out.append(
            {
                "severity": str(entry.get("severity", "warning")),
                "source": "ai",
                "field_id": None,
                "message": str(entry.get("text", "")),
                "raw_value": None,
                "threshold": None,
            }
        )
    return out
