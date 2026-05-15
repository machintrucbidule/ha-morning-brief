"""compute/ — availability gate, comparisons, anomaly detection.

See MORNING_BRIEF_SPEC.md Sections 9, 11, 12.
"""

from .anomaly import detect_anomaly
from .availability import apply_gate
from .comparisons import (
    compare_rolling_avg,
    compare_rolling_max,
    compare_rolling_min,
    compare_same_week_last_year,
    compare_same_weekday_last_week,
    compare_target_value,
    compare_trend,
    compare_yesterday,
    compute_interpretation,
    evaluate_comparisons,
)

__all__ = [
    "apply_gate",
    "compare_rolling_avg",
    "compare_rolling_max",
    "compare_rolling_min",
    "compare_same_week_last_year",
    "compare_same_weekday_last_week",
    "compare_target_value",
    "compare_trend",
    "compare_yesterday",
    "compute_interpretation",
    "detect_anomaly",
    "evaluate_comparisons",
]
