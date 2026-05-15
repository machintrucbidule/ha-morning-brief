"""Per-field anomaly detection (Section 12, D15).

Three real detection modes plus the ``none`` no-op. All take the current
numeric value plus optional rolling history (for z_score / pct_change)
and return an :class:`types.AnomalyResult`. Severity defaults:
- z_score: ≥3σ → critical, ≥2σ → warning, else info
- static_threshold / pct_change: user-configurable, default warning
"""

from __future__ import annotations

import logging
import math
from typing import Any

from ..const import (
    ANOMALY_NONE,
    ANOMALY_PCT_CHANGE,
    ANOMALY_SEVERITY_CRITICAL,
    ANOMALY_SEVERITY_INFO,
    ANOMALY_SEVERITY_WARNING,
    ANOMALY_STATIC_THRESHOLD,
    ANOMALY_Z_SCORE,
    DEFAULT_Z_SCORE_SIGMAS,
)
from ..types import AnomalyResult

_LOGGER = logging.getLogger(__name__)

_NONE_RESULT = AnomalyResult(
    detected=False,
    severity=ANOMALY_SEVERITY_INFO,
    mode=ANOMALY_NONE,
    message_key="",
)


def _z_severity(z: float, threshold: float) -> str:
    """Map a z-score to a severity bucket (3σ → critical, 2σ → warning)."""
    if z >= 3.0:
        return ANOMALY_SEVERITY_CRITICAL
    if z >= 2.0:
        return ANOMALY_SEVERITY_WARNING
    _ = threshold
    return ANOMALY_SEVERITY_INFO


def _detect_z_score(
    config: dict[str, Any], current: float, history: list[float]
) -> AnomalyResult:
    sigmas = float(config.get("sigmas", DEFAULT_Z_SCORE_SIGMAS))
    if len(history) < 2:
        return AnomalyResult(
            detected=False,
            severity=ANOMALY_SEVERITY_INFO,
            mode=ANOMALY_Z_SCORE,
            message_key="",
        )
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std = math.sqrt(variance)
    if std == 0:
        return AnomalyResult(
            detected=False,
            severity=ANOMALY_SEVERITY_INFO,
            mode=ANOMALY_Z_SCORE,
            message_key="",
        )
    z = abs(current - mean) / std
    if z <= sigmas:
        return AnomalyResult(
            detected=False,
            severity=ANOMALY_SEVERITY_INFO,
            mode=ANOMALY_Z_SCORE,
            message_key="",
            raw_value=current,
            threshold=sigmas,
        )
    return AnomalyResult(
        detected=True,
        severity=_z_severity(z, sigmas),
        mode=ANOMALY_Z_SCORE,
        message_key="anomaly.z_score",
        raw_value=current,
        threshold=sigmas,
    )


def _detect_static_threshold(
    config: dict[str, Any], current: float
) -> AnomalyResult:
    min_v = config.get("min_value")
    max_v = config.get("max_value")
    severity_below = str(
        config.get("severity_below", ANOMALY_SEVERITY_WARNING)
    )
    severity_above = str(
        config.get("severity_above", ANOMALY_SEVERITY_WARNING)
    )
    if min_v is not None and current < float(min_v):
        return AnomalyResult(
            detected=True,
            severity=severity_below,
            mode=ANOMALY_STATIC_THRESHOLD,
            message_key="anomaly.below_min",
            raw_value=current,
            threshold=float(min_v),
        )
    if max_v is not None and current > float(max_v):
        return AnomalyResult(
            detected=True,
            severity=severity_above,
            mode=ANOMALY_STATIC_THRESHOLD,
            message_key="anomaly.above_max",
            raw_value=current,
            threshold=float(max_v),
        )
    return AnomalyResult(
        detected=False,
        severity=ANOMALY_SEVERITY_INFO,
        mode=ANOMALY_STATIC_THRESHOLD,
        message_key="",
        raw_value=current,
        threshold=None,
    )


def _detect_pct_change(
    config: dict[str, Any], current: float, history: list[float]
) -> AnomalyResult:
    if not history:
        return AnomalyResult(
            detected=False,
            severity=ANOMALY_SEVERITY_INFO,
            mode=ANOMALY_PCT_CHANGE,
            message_key="",
        )
    pct = float(config["pct"])
    mean = sum(history) / len(history)
    if mean == 0:
        return AnomalyResult(
            detected=False,
            severity=ANOMALY_SEVERITY_INFO,
            mode=ANOMALY_PCT_CHANGE,
            message_key="",
        )
    change_pct = abs((current - mean) / mean) * 100
    if change_pct <= pct:
        return AnomalyResult(
            detected=False,
            severity=ANOMALY_SEVERITY_INFO,
            mode=ANOMALY_PCT_CHANGE,
            message_key="",
            raw_value=current,
            threshold=pct,
        )
    severity = str(config.get("severity", ANOMALY_SEVERITY_WARNING))
    return AnomalyResult(
        detected=True,
        severity=severity,
        mode=ANOMALY_PCT_CHANGE,
        message_key="anomaly.pct_change",
        raw_value=current,
        threshold=pct,
    )


def detect_anomaly(
    config: dict[str, Any],
    current: float | None,
    history: list[float] | None = None,
) -> AnomalyResult:
    """Dispatch to the configured mode. ``None`` current → no detection.

    Args:
        config: per-field anomaly block (Section 12.1). Must contain ``mode``.
        current: the field's current numeric value, or None.
        history: rolling daily-mean history (only z_score and pct_change use it).

    Returns:
        An ``AnomalyResult``. ``detected=False`` for the ``none`` mode,
        missing current, or insufficient history.
    """
    mode = str(config.get("mode", ANOMALY_NONE))
    if mode == ANOMALY_NONE or current is None:
        return AnomalyResult(
            detected=False,
            severity=ANOMALY_SEVERITY_INFO,
            mode=mode,
            message_key="",
        )
    hist = history or []
    if mode == ANOMALY_Z_SCORE:
        return _detect_z_score(config, current, hist)
    if mode == ANOMALY_STATIC_THRESHOLD:
        return _detect_static_threshold(config, current)
    if mode == ANOMALY_PCT_CHANGE:
        return _detect_pct_change(config, current, hist)
    _LOGGER.warning("Unknown anomaly mode: %s — treated as none", mode)
    return _NONE_RESULT
