"""Tests for reports/canonical.py (Section 14.5 + 15)."""

from __future__ import annotations

from datetime import date

from custom_components.morning_brief.reports.base import ResolvedField
from custom_components.morning_brief.reports.canonical import build_canonical_json
from custom_components.morning_brief.types import AnomalyResult, FieldValue


def _category() -> dict[str, str | int | bool]:
    return {
        "id": "health",
        "label": "Santé",
        "icon": "💪",
        "order": 10,
        "display_when_empty": False,
    }


def _resolved() -> ResolvedField:
    return ResolvedField(
        id="weight",
        label="Poids",
        icon="⚖️",
        order=10,
        category_id="health",
        provider_type="instantaneous",
        direction_preference="lower_is_better",
        value=FieldValue(raw=75.5, unit="kg"),
    )


def test_canonical_envelope_has_required_top_level_keys() -> None:
    out = build_canonical_json(
        instance_id="abc",
        instance_name="Brief",
        report_type="morning",
        language="fr",
        logical_date=date(2026, 5, 15),
        cal_offset=0,
        logical_day_strategy="fixed_cutoff",
        fields_resolved=[],
        categories=[],
        ai_envelope=None,
        ai_provider="disabled",
    )
    assert out["schema_version"] == 1
    for key in (
        "meta",
        "alerts",
        "categories",
        "ai_output",
        "ha_health",
        "previous_briefs_refs",
    ):
        assert key in out


def test_meta_propagates_inputs() -> None:
    out = build_canonical_json(
        instance_id="entry-1",
        instance_name="Brief matinal",
        report_type="morning",
        language="fr",
        logical_date=date(2026, 5, 15),
        cal_offset=1,
        logical_day_strategy="sleep_sensor",
        fields_resolved=[],
        categories=[],
        ai_envelope=None,
        ai_provider="anthropic_direct",
        ai_status="degraded",
        ai_error="http_429",
        duration_ms=1234,
    )
    meta = out["meta"]
    assert meta["instance_id"] == "entry-1"
    assert meta["instance_name"] == "Brief matinal"
    assert meta["report_type"] == "morning"
    assert meta["language"] == "fr"
    assert meta["logical_date"] == "2026-05-15"
    assert meta["logical_day_offset"] == 1
    assert meta["logical_day_strategy"] == "sleep_sensor"
    assert meta["ai_status"] == "degraded"
    assert meta["ai_provider"] == "anthropic_direct"
    assert meta["ai_error"] == "http_429"
    assert meta["duration_ms"] == 1234


def test_fields_grouped_by_category_and_sorted_by_order() -> None:
    rf_a = _resolved()
    rf_b = ResolvedField(
        id="hr",
        label="HR",
        icon="💓",
        order=5,
        category_id="health",
        provider_type="instantaneous",
        direction_preference="lower_is_better",
        value=FieldValue(raw=64, unit="bpm"),
    )
    out = build_canonical_json(
        instance_id="x",
        instance_name="x",
        report_type="morning",
        language="en",
        logical_date=date(2026, 5, 15),
        cal_offset=0,
        logical_day_strategy="fixed_cutoff",
        fields_resolved=[rf_a, rf_b],
        categories=[_category()],
        ai_envelope=None,
        ai_provider=None,
    )
    cat = out["categories"][0]
    assert cat["id"] == "health"
    assert [f["id"] for f in cat["fields"]] == ["hr", "weight"]


def test_empty_category_dropped_unless_display_when_empty() -> None:
    cat_visible = {**_category(), "display_when_empty": True}
    out = build_canonical_json(
        instance_id="x",
        instance_name="x",
        report_type="morning",
        language="en",
        logical_date=date(2026, 5, 15),
        cal_offset=0,
        logical_day_strategy="fixed_cutoff",
        fields_resolved=[],
        categories=[_category(), cat_visible],
        ai_envelope=None,
        ai_provider=None,
    )
    # First category dropped (display_when_empty=False); second kept.
    assert len(out["categories"]) == 1
    assert out["categories"][0]["display_when_empty"] is True


def test_detected_anomaly_emits_alert() -> None:
    rf = _resolved()
    rf.anomaly = AnomalyResult(
        detected=True,
        severity="warning",
        mode="static_threshold",
        message="Below 70 kg",
        raw_value=68.0,
        threshold=70.0,
    )
    out = build_canonical_json(
        instance_id="x",
        instance_name="x",
        report_type="morning",
        language="en",
        logical_date=date(2026, 5, 15),
        cal_offset=0,
        logical_day_strategy="fixed_cutoff",
        fields_resolved=[rf],
        categories=[_category()],
        ai_envelope=None,
        ai_provider=None,
    )
    alerts = out["alerts"]
    assert any(
        a["source"] == "anomaly" and a["field_id"] == "weight" for a in alerts
    )


def test_ai_alerts_from_envelope_are_merged() -> None:
    envelope = {
        "alertes_formulees": [{"text": "Heads up", "severity": "warning"}],
        "insights": {"health": "Sane week."},
        "weather_synthesis": "",
        "verdict": "Looks fine.",
    }
    out = build_canonical_json(
        instance_id="x",
        instance_name="x",
        report_type="morning",
        language="en",
        logical_date=date(2026, 5, 15),
        cal_offset=0,
        logical_day_strategy="fixed_cutoff",
        fields_resolved=[],
        categories=[],
        ai_envelope=envelope,
        ai_provider="ha_ai_task",
    )
    assert {a["source"] for a in out["alerts"]} == {"ai"}
    assert out["ai_output"]["category_insights"] == {"health": "Sane week."}
    assert out["ai_output"]["verdict"] == "Looks fine."


def test_field_value_dict_carries_stale_and_unit() -> None:
    rf = _resolved()
    rf.value = FieldValue(raw=None, unit="kg", stale=True, stale_reason="no_data")
    out = build_canonical_json(
        instance_id="x",
        instance_name="x",
        report_type="morning",
        language="en",
        logical_date=date(2026, 5, 15),
        cal_offset=0,
        logical_day_strategy="fixed_cutoff",
        fields_resolved=[rf],
        categories=[_category()],
        ai_envelope=None,
        ai_provider=None,
    )
    field_dict = out["categories"][0]["fields"][0]
    assert field_dict["value"]["stale"] is True
    assert field_dict["value"]["stale_reason"] == "no_data"
    assert field_dict["value"]["unit"] == "kg"
    assert field_dict["value"]["raw"] is None
