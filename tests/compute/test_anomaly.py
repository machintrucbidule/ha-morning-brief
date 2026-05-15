"""Tests for compute/anomaly.py (Section 12)."""

from __future__ import annotations

from custom_components.morning_brief.compute.anomaly import detect_anomaly

# --------------------------------------------------------------------------- #
# none
# --------------------------------------------------------------------------- #


def test_none_mode_never_detects() -> None:
    r = detect_anomaly({"mode": "none"}, current=999.0, history=[1.0, 2.0])
    assert r.detected is False
    assert r.mode == "none"


def test_unknown_mode_treated_as_none() -> None:
    r = detect_anomaly({"mode": "blob"}, current=1.0, history=[])
    assert r.detected is False


def test_missing_current_returns_no_detection() -> None:
    r = detect_anomaly({"mode": "z_score"}, current=None, history=[1.0, 2.0])
    assert r.detected is False


# --------------------------------------------------------------------------- #
# z_score
# --------------------------------------------------------------------------- #


def test_z_score_within_threshold_not_detected() -> None:
    """Mean=10, std≈1.6; value=11 → z≈0.6 < 2σ."""
    history = [8.0, 9.0, 10.0, 11.0, 12.0]
    r = detect_anomaly({"mode": "z_score", "sigmas": 2}, current=11.0, history=history)
    assert r.detected is False


def test_z_score_above_threshold_detected_as_warning() -> None:
    """Tight history around 10, value=15 → z≈2.2σ → warning."""
    history = [9.5, 9.8, 10.0, 10.2, 10.5]
    r = detect_anomaly({"mode": "z_score", "sigmas": 2.0}, current=15.0, history=history)
    assert r.detected is True
    assert r.severity in ("warning", "critical")


def test_z_score_3_sigma_or_above_is_critical() -> None:
    history = [9.5, 9.8, 10.0, 10.2, 10.5]
    r = detect_anomaly({"mode": "z_score", "sigmas": 2.0}, current=20.0, history=history)
    assert r.detected is True
    assert r.severity == "critical"


def test_z_score_zero_std_not_detected() -> None:
    """All same value → std=0, no detection (avoid div-by-zero)."""
    r = detect_anomaly(
        {"mode": "z_score", "sigmas": 2.0}, current=99.0, history=[10.0, 10.0, 10.0]
    )
    assert r.detected is False


def test_z_score_too_short_history_not_detected() -> None:
    r = detect_anomaly({"mode": "z_score", "sigmas": 2.0}, current=99.0, history=[10.0])
    assert r.detected is False


# --------------------------------------------------------------------------- #
# static_threshold
# --------------------------------------------------------------------------- #


def test_static_threshold_below_min_detected() -> None:
    r = detect_anomaly(
        {"mode": "static_threshold", "min_value": 300, "severity_below": "warning"},
        current=250.0,
        history=[],
    )
    assert r.detected is True
    assert r.severity == "warning"
    assert r.threshold == 300.0


def test_static_threshold_above_max_detected() -> None:
    r = detect_anomaly(
        {"mode": "static_threshold", "max_value": 100, "severity_above": "critical"},
        current=120.0,
        history=[],
    )
    assert r.detected is True
    assert r.severity == "critical"
    assert r.threshold == 100.0


def test_static_threshold_within_range_not_detected() -> None:
    r = detect_anomaly(
        {"mode": "static_threshold", "min_value": 0, "max_value": 100},
        current=50.0,
        history=[],
    )
    assert r.detected is False


def test_static_threshold_no_bounds_never_detects() -> None:
    """Both min and max missing → no detection (config means nothing to check)."""
    r = detect_anomaly({"mode": "static_threshold"}, current=9999.0, history=[])
    assert r.detected is False


# --------------------------------------------------------------------------- #
# pct_change_vs_rolling_avg
# --------------------------------------------------------------------------- #


def test_pct_change_above_threshold_detected() -> None:
    """Mean=100, current=160 → +60% > 50% → detected."""
    r = detect_anomaly(
        {"mode": "pct_change_vs_rolling_avg", "pct": 50, "window_days": 14},
        current=160.0,
        history=[100.0, 100.0, 100.0],
    )
    assert r.detected is True


def test_pct_change_below_threshold_not_detected() -> None:
    r = detect_anomaly(
        {"mode": "pct_change_vs_rolling_avg", "pct": 50},
        current=110.0,
        history=[100.0, 100.0, 100.0],
    )
    assert r.detected is False


def test_pct_change_empty_history_not_detected() -> None:
    r = detect_anomaly(
        {"mode": "pct_change_vs_rolling_avg", "pct": 50},
        current=100.0,
        history=[],
    )
    assert r.detected is False


def test_pct_change_zero_mean_not_detected() -> None:
    """Avoid division by zero when the rolling history averages to 0."""
    r = detect_anomaly(
        {"mode": "pct_change_vs_rolling_avg", "pct": 50},
        current=10.0,
        history=[0.0, 0.0],
    )
    assert r.detected is False


def test_pct_change_custom_severity() -> None:
    r = detect_anomaly(
        {"mode": "pct_change_vs_rolling_avg", "pct": 50, "severity": "critical"},
        current=160.0,
        history=[100.0],
    )
    assert r.severity == "critical"
