"""Constants for the morning_brief integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "morning_brief"

# Storage
STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = "morning_brief"  # full key: morning_brief_<entry_id>
DEFAULT_RETENTION: Final = 30
MIN_RETENTION: Final = 5
MAX_RETENTION: Final = 365

# Schema versioning for the canonical JSON document
CANONICAL_SCHEMA_VERSION: Final = 1

# Sensor attribute size cap. HA's sensor attribute payload is limited; ~16 KB
# is the safe ceiling. Above it, truncate the attributes and serve the full
# payload via the morning_brief.get_last_brief service. (Spec D18, G13.)
SENSOR_ATTRIBUTE_BYTE_LIMIT: Final = 16_000

# Report types (D12)
REPORT_TYPE_MORNING: Final = "morning"
REPORT_TYPE_EVENING: Final = "evening"
REPORT_TYPE_WEEKLY: Final = "weekly"
REPORT_TYPES: Final = (REPORT_TYPE_MORNING, REPORT_TYPE_EVENING, REPORT_TYPE_WEEKLY)

# Field provider types (D4) — closed V1 list. Adding a new type in V2 means
# adding a new file in providers/ and registering it in providers/__init__.py.
PROVIDER_CUMULATIVE: Final = "cumulative"
PROVIDER_INSTANTANEOUS: Final = "instantaneous"
PROVIDER_EVENT_BASED: Final = "event_based"
PROVIDER_STATE: Final = "state"
PROVIDER_DURATION: Final = "duration"
PROVIDER_CALENDAR: Final = "calendar"
PROVIDER_WEATHER: Final = "weather"
PROVIDER_MANUAL: Final = "manual"
PROVIDER_TYPES: Final = (
    PROVIDER_CUMULATIVE,
    PROVIDER_INSTANTANEOUS,
    PROVIDER_EVENT_BASED,
    PROVIDER_STATE,
    PROVIDER_DURATION,
    PROVIDER_CALENDAR,
    PROVIDER_WEATHER,
    PROVIDER_MANUAL,
)

# Logical day strategies (D6)
LOGICAL_DAY_FIXED_CUTOFF: Final = "fixed_cutoff"
LOGICAL_DAY_SLEEP_SENSOR: Final = "sleep_sensor"
LOGICAL_DAY_MANUAL: Final = "manual"
LOGICAL_DAY_STRATEGIES: Final = (
    LOGICAL_DAY_FIXED_CUTOFF,
    LOGICAL_DAY_SLEEP_SENSOR,
    LOGICAL_DAY_MANUAL,
)
DEFAULT_CUTOFF_HOUR: Final = 4
DEFAULT_HARD_FALLBACK_HOUR: Final = 12
DEFAULT_LOOKBACK_HOURS: Final = 36
DEFAULT_MIN_SLEEP_DURATION_MINUTES: Final = 120

# Trigger levels (D7)
TRIGGER_SCHEDULE: Final = "schedule"
TRIGGER_SENSOR_BASED: Final = "sensor_based"
TRIGGER_EXTERNAL: Final = "external"
TRIGGER_LEVELS: Final = (TRIGGER_SCHEDULE, TRIGGER_SENSOR_BASED, TRIGGER_EXTERNAL)
DEFAULT_SENSOR_BASED_DELAY_MINUTES: Final = 30
DEFAULT_FALLBACK_HOUR: Final = 12

# AI providers (D8)
AI_PROVIDER_HA_AI_TASK: Final = "ha_ai_task"
AI_PROVIDER_ANTHROPIC_DIRECT: Final = "anthropic_direct"
AI_PROVIDER_OPENAI_DIRECT: Final = "openai_direct"
AI_PROVIDER_DISABLED: Final = "disabled"
AI_PROVIDER_TYPES: Final = (
    AI_PROVIDER_HA_AI_TASK,
    AI_PROVIDER_ANTHROPIC_DIRECT,
    AI_PROVIDER_OPENAI_DIRECT,
    AI_PROVIDER_DISABLED,
)
# Retry policy (D8): 3 attempts, exponential backoff starting at 60s → 60, 120, 240.
AI_RETRY_MAX_ATTEMPTS: Final = 3
AI_RETRY_BASE_DELAY_SECONDS: Final = 60

# AI status enum carried in the canonical JSON's meta.
AI_STATUS_OK: Final = "ok"
AI_STATUS_DEGRADED: Final = "degraded"
AI_STATUS_DISABLED: Final = "disabled"

# Comparison types (D14) — V1 closed list of 8.
COMPARISON_YESTERDAY: Final = "yesterday"
COMPARISON_SAME_WEEKDAY_LAST_WEEK: Final = "same_weekday_last_week"
COMPARISON_ROLLING_AVG: Final = "rolling_avg"
COMPARISON_ROLLING_MIN: Final = "rolling_min"
COMPARISON_ROLLING_MAX: Final = "rolling_max"
COMPARISON_TARGET_VALUE: Final = "target_value"
COMPARISON_TREND: Final = "trend"
COMPARISON_SAME_WEEK_LAST_YEAR: Final = "same_week_last_year"
COMPARISON_TYPES: Final = (
    COMPARISON_YESTERDAY,
    COMPARISON_SAME_WEEKDAY_LAST_WEEK,
    COMPARISON_ROLLING_AVG,
    COMPARISON_ROLLING_MIN,
    COMPARISON_ROLLING_MAX,
    COMPARISON_TARGET_VALUE,
    COMPARISON_TREND,
    COMPARISON_SAME_WEEK_LAST_YEAR,
)
# Comparison status enum carried in the canonical JSON per comparison.
STATUS_OK: Final = "ok"
STATUS_PARTIAL: Final = "partial"
STATUS_INSUFFICIENT_HISTORY: Final = "insufficient_history"
STATUS_UNRELIABLE: Final = "unreliable"
STATUS_NOT_APPLICABLE: Final = "not_applicable"
# Gap-handling thresholds (D11): <30% missing → partial, ≥30% missing → unreliable.
PARTIAL_GAP_THRESHOLD: Final = 0.30

# Recorder retention fallback. The recorder's `purge_keep_days` is the truth
# source (G7), but if we cannot read it we fall back to HA's documented default.
DEFAULT_RECORDER_RETENTION_DAYS: Final = 10

# History layer aggregations (Section 10). The LTS wrapper maps these to
# statistic types; the short-term wrapper computes them in-process.
HISTORY_AGG_MEAN: Final = "mean"
HISTORY_AGG_CHANGE: Final = "change"
HISTORY_AGG_SUM: Final = "sum"
HISTORY_AGG_MAX: Final = "max"
HISTORY_AGG_MIN: Final = "min"
HISTORY_AGG_LAST: Final = "last"  # short-term only — LTS has no "last" stat type
HISTORY_AGGREGATIONS: Final = (
    HISTORY_AGG_MEAN,
    HISTORY_AGG_CHANGE,
    HISTORY_AGG_SUM,
    HISTORY_AGG_MAX,
    HISTORY_AGG_MIN,
    HISTORY_AGG_LAST,
)

# Event detector defaults (D23, G1).
DEFAULT_EVENT_EPSILON: Final = 0.0
DEFAULT_MIN_DEBOUNCE_SECONDS: Final = 300

# Anomaly modes (D15)
ANOMALY_NONE: Final = "none"
ANOMALY_Z_SCORE: Final = "z_score"
ANOMALY_STATIC_THRESHOLD: Final = "static_threshold"
ANOMALY_PCT_CHANGE: Final = "pct_change_vs_rolling_avg"
ANOMALY_MODES: Final = (
    ANOMALY_NONE,
    ANOMALY_Z_SCORE,
    ANOMALY_STATIC_THRESHOLD,
    ANOMALY_PCT_CHANGE,
)
ANOMALY_SEVERITY_INFO: Final = "info"
ANOMALY_SEVERITY_WARNING: Final = "warning"
ANOMALY_SEVERITY_CRITICAL: Final = "critical"
ANOMALY_SEVERITIES: Final = (
    ANOMALY_SEVERITY_INFO,
    ANOMALY_SEVERITY_WARNING,
    ANOMALY_SEVERITY_CRITICAL,
)
DEFAULT_Z_SCORE_SIGMAS: Final = 2.0
DEFAULT_Z_SCORE_WINDOW_DAYS: Final = 14

# Weekly aggregations (D13)
WEEKLY_AGG_SUM: Final = "sum"
WEEKLY_AGG_MEAN: Final = "mean"
WEEKLY_AGG_MAX: Final = "max"
WEEKLY_AGG_MIN: Final = "min"
WEEKLY_AGG_LATEST: Final = "latest"
WEEKLY_AGG_NONE: Final = "none"
WEEKLY_AGGREGATIONS: Final = (
    WEEKLY_AGG_SUM,
    WEEKLY_AGG_MEAN,
    WEEKLY_AGG_MAX,
    WEEKLY_AGG_MIN,
    WEEKLY_AGG_LATEST,
    WEEKLY_AGG_NONE,
)

# Direction preference for fields.
DIRECTION_HIGHER_IS_BETTER: Final = "higher_is_better"
DIRECTION_LOWER_IS_BETTER: Final = "lower_is_better"
DIRECTION_NEUTRAL: Final = "neutral"
DIRECTION_PREFERENCES: Final = (
    DIRECTION_HIGHER_IS_BETTER,
    DIRECTION_LOWER_IS_BETTER,
    DIRECTION_NEUTRAL,
)

# Languages (D20). FR + EN at launch. Adding a language means dropping a JSON
# file in translations/ — the loader picks it up automatically.
LANGUAGE_EN: Final = "en"
LANGUAGE_FR: Final = "fr"
DEFAULT_LANGUAGE: Final = LANGUAGE_EN  # fallback when hass.config.language is unknown
SUPPORTED_LANGUAGES: Final = (LANGUAGE_EN, LANGUAGE_FR)

# Subentry types (D3)
SUBENTRY_TYPE_FIELD: Final = "field"
SUBENTRY_TYPE_CATEGORY: Final = "category"

# Stale reason strings exposed in FieldValue.stale_reason. Kept as constants so
# the card and renderings can map them to translated copy.
STALE_NO_DATA: Final = "no_data"
STALE_NO_EVENT_TODAY: Final = "no_event_today"
STALE_AWAITING_AVAILABILITY: Final = "awaiting_availability"
STALE_GATE_SENSOR_UNAVAILABLE: Final = "gate_sensor_unavailable"
STALE_NO_DATA_FOR_DATE: Final = "no_data_for_date"

# Events emitted on the HA event bus.
EVENT_BRIEF_GENERATED: Final = "morning_brief_generated"
EVENT_AI_FAILED: Final = "morning_brief_ai_failed"

# Sensor entity state values.
SENSOR_STATE_OK: Final = "ok"
SENSOR_STATE_DEGRADED: Final = "degraded"
SENSOR_STATE_ERROR: Final = "error"
SENSOR_STATE_STALE: Final = "stale"
SENSOR_STATE_NO_DATA: Final = "no_data"
