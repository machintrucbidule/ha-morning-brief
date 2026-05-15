# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial repo scaffolding.
- Foundation skeleton: manifest, const, types, exceptions, translations skeleton, coordinator skeleton, store with FIFO rotation, setup_entry / unload_entry, tests for store rotation.
- History layer (Section 10): `history/lts.py` (LTS daily wrapper), `history/short_term.py` (raw + per-day aggregator), `history/event_detector.py` (filter unavailable/unknown, epsilon dedup, debounce), `history/hybrid.py` (LTS-first orchestrator with short-term gap-fill, recorder-retention-aware, D11 status enum). 39 tests covering Section 10.7 scenarios.
- Field providers (Section 8): `FieldProvider` ABC + registry + factory in `providers/`. All 8 V1 provider types implemented: `instantaneous`, `cumulative`, `event_based`, `state`, `duration`, `calendar`, `weather`, `manual`. Each with config schema, `validate_config`, and `detect_from_entity` heuristic. Comprehensive tests including factory + parametrised happy-path for every type.
- Logical day strategies (Section 7): `LogicalDayStrategy` ABC + registry. Three strategies: `fixed_cutoff` (default, hour-based), `sleep_sensor` (recorder-driven wake detection with nap filter and hard fallback), `manual` (advance via service). Each returns `(logical_date, cal_offset)`.
- Triggers (Section 16): `ScheduleTrigger` (cron-style time + days-of-week) and `SensorBasedTrigger` (state-machine: trigger sensor → delay countdown → opt-out shortcut, plus daily fallback hour). External (Level 3) is service-only — no implementation needed.
- Compute layer (Sections 9, 11, 12): `compute/availability.py` (`apply_gate`, transverse and provider-agnostic per D5/G5), `compute/comparisons.py` (all 8 V1 comparison types — yesterday, same_weekday_last_week, rolling_avg/min/max, target_value, trend, same_week_last_year — plus a dispatcher and the interpretation helper), `compute/anomaly.py` (`detect_anomaly` covering all 3 detection modes plus the `none` no-op).
- AI layer (Section 13): `AIProvider` ABC + registry/factory + 4 V1 providers — `disabled` (degraded mode, returns empty valid JSON envelope), `ha_ai_task` (delegates to any `ai_task.*` HA entity), `anthropic_direct` (direct Anthropic Messages API via aiohttp), `openai_direct` (direct OpenAI Chat Completions). `generate_with_retry` wraps any provider with 3-attempt exponential back-off + JSON validation (D8, G14). Jinja2 prompt-template loader with `StrictUndefined` and three English templates (`morning_v1.txt`, `evening_v1.txt`, `weekly_v1.txt`) that embed the target language so the model replies in the right one (D20).
