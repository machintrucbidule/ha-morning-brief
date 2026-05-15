# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0-rc.2] — 2026-05-15

### Fixed

- **Options flow 500 error on HA ≥ 2024.12** — `OptionsFlow.config_entry`
  became a read-only property; our `__init__` was still trying to assign
  it, raising `AttributeError`. Removed the `__init__` and switched to
  the parameterless constructor pattern HA now expects. Discovered during
  the first live-HA install of v1.0.0-rc.1.
- **`manifest.json` version mismatch** — was still `0.0.1`, preventing
  HACS from detecting updates. Bumped to `1.0.0rc2` (PEP 440 form
  matching the git tag).

## [1.0.0-rc.1] — 2026-05-15

First release candidate. All 12 phases of the build plan complete. Final
`v1.0.0` is gated on a manual end-to-end test against a live HA instance
(per Section 37 acceptance criteria) and replacement of the placeholder
brand icons and preview screenshot.

### Added

- Phase 12 — Polish & release prep: pytest-cov + per-module coverage report
  in CI (≥70% global floor), `docs/img/preview.png` placeholder, end-of-
  session ritual fixes (refreshed Open questions / blockers, restored
  chronological session-log order, fixed two factual errors in Phase 11
  docs: `claude-sonnet-4-7` → `claude-sonnet-4-6`, `instance_id` →
  `entry_id`).
- Initial repo scaffolding (Phase 1).
- Phase 1 — Foundation: manifest, const, types, exceptions, translations skeleton, coordinator skeleton, FIFO store, init/unload/remove.
- Phase 2 — History layer: LTS daily wrapper, short-term aggregator, event detector with debounce/dedup, hybrid orchestrator with recorder-retention awareness, D11 status enum.
- Phase 3 — Providers: 8 V1 providers (cumulative, instantaneous, manual, state, event_based, duration, calendar, weather) + factory + per-provider tests.
- Phase 4 — Logical day & triggers: 3 strategies (fixed_cutoff, sleep_sensor, manual), L1 schedule trigger, L2 sensor-based trigger with opt-out + fallback.
- Phase 5 — Compute: availability gate (orthogonal), 8 comparison types + dispatcher, 3 anomaly modes + dispatcher.
- Phase 6 — AI: AIProvider ABC + 4 backends (disabled / ha_ai_task / anthropic_direct / openai_direct), 3-attempt retry with exponential backoff, Jinja2 prompt loader with StrictUndefined, prompts for morning/evening/weekly.
- Phase 7 — Reports & renderings: canonical JSON builder per Section 15, MorningReport / EveningReport / WeeklyReport, markdown fallback, notification short-body.
- Phase 8 — Config flow & subentries: 6-step initial flow, 8-section options menu, field subentry (7 steps), category subentry, translations EN+FR at 133 keys.
- Phase 9 — Services, entities, events: 8 services, main sensor with D18 truncation, status sensor, generate/preview buttons, full wiring in `__init__.py`.
- Phase 11 — Docs: README (20 sections), `docs/architecture.md`, `docs/providers.md`, `docs/triggers.md`, `docs/ai_providers.md`, `docs/multilanguage.md`, 4 example YAMLs (2 Lovelace + 1 L3 automation + 1 full config export), 2 blueprints (`trigger_on_schedule.yaml`, `trigger_on_wake.yaml`).
