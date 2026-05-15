# CLAUDE.md — home-assistant-morning-brief

## Read this first, every session

This file is your persistent memory. Read it at the start of every session BEFORE doing anything else. Update the "Current status", "Open questions", and "Session log" sections at the END of every session.

The full specification lives in `MORNING_BRIEF_SPEC.md` (committed at the project root next to this file). When in doubt about ANY behavior, refer to the spec. Do not infer.

## Project context

Python custom_component for Home Assistant. Generates configurable AI-enriched daily/evening/weekly briefs from user-defined sensors. HACS-public. Companion frontend lives in the sibling repo `morning-brief-card`.

## Architecture decisions (IMMUTABLE — do not change without user approval logged in DECISIONS.md)

**D1. HACS public distribution, two separate repos.** The integration and the card are distributed as independent HACS repositories. They share a contract (the canonical JSON schema, Section 15) but have independent versioning and release cycles. Cross-references in READMEs.

**D2. HA Core minimum version.** Target the latest stable HA Core version that supports BOTH `config_entries.subentries` AND `ai_task` component. Verify at scaffold time, document in `manifest.json`.

**D3. Subentries architecture for dynamic configuration.** The integration declares 2 subentry types: `field` and `category`. Each has its own flow handler. Instances of subentries (= configured fields, created categories) are dynamic, added/edited/deleted by the user via the HA UI. The native HA UI handles add/edit/delete lifecycle.

**D4. 8 field provider types (V1 closed list).** The closed V1 list is: `cumulative`, `instantaneous`, `event_based`, `state`, `duration`, `calendar`, `weather`, `manual`. Adding a new provider type in V2 requires a new file in `providers/` and registration in the factory — no other changes.

**D5. Availability gate is orthogonal.** Every provider type supports an optional `availability_gate` config: `{entity_id, expected_state}`. When the gate is not satisfied at evaluation time, the provider returns the previous valid day's value with `stale: true, stale_reason: "awaiting_availability"`. The gate is NOT a provider type — it's a transverse feature.

**D6. Three logical-day strategies.** `fixed_cutoff` (parameter: cutoff_hour, default 04:00), `sleep_sensor` (parameters: sensor binary_sensor, awake_state, hard_fallback_hour for cases where no sleep is detected within 36h), `manual` (advanced via service call `morning_brief.advance_day`). Strategy is per-instance, configured at instance creation. Returns `(logical_date, cal_offset)` where `cal_offset=0` means logical date matches calendar date, `cal_offset=1` means user hasn't transitioned to today yet.

**D7. Three trigger levels (coexist, configurable per instance).** L1: schedule (cron-style, time + days-of-week). L2: sensor-based with delay and opt-outs (trigger sensor + delay + opt-out sensors that fire early if changed + fallback hour). L3: external (service-only, user writes their own automation). All three ultimately call the same service `morning_brief.generate.<instance>`. Blueprints provided for L1 and L2 common cases.

**D8. Four AI provider implementations.** `ha_ai_task` (uses any `ai_task.*` entity available in HA), `anthropic_direct` (direct API with user-supplied key), `openai_direct` (direct API with user-supplied key), `disabled` (degraded mode, brief without AI enrichment). All inherit `AIProvider` ABC. Retry logic: 3 attempts, exponential backoff with base 1 minute, asynchronous (does not block the coordinator).

**D9. AI failure does not break the brief.** If AI fails after all retries: `ai_status: degraded`, `ai_output` is empty (insights blank, weather_synthesis blank, verdict blank). Brief is still produced, persisted, and notified. The card and renderings handle the degraded case gracefully.

**D10. Hybrid history layer prefers LTS.** For comparisons requiring historical data: prefer LTS (long-term statistics) over short-term history when both are available. Detect LTS availability per sensor via `state_class` attribute. Detect recorder retention period via the recorder config. Compute the actual coverage for the requested window. On conflict (same date, different value): LTS wins. Index timeseries by date (dict), NEVER by list position.

**D11. Gap handling in history.** For each comparison: count missing days vs requested window. `0 missing → status: ok`. `0 < missing < 30% → status: partial`, return value with `days_used` field. `≥ 30% missing → status: unreliable`, the card MAY display "—" or hide the comparison. If sensor history doesn't cover the window at all: `status: insufficient_history`.

**D12. Three report types, one instance per type.** Instance creation chooses one of `morning | evening | weekly`. Each instance is independent (independent config flow, options, fields, categories, AI provider, etc.). To share fields across reports, the "copy fields/categories" mechanism is offered at instance creation (one-shot duplication, not a live link).

**D13. Weekly aggregation per field.** For weekly reports, each field declares a `weekly_aggregation` enum: `sum | mean | max | min | latest | none`. The UI shows this field only if the field is `visible_in: weekly`. Smart defaults per provider type: cumulative→sum, instantaneous→mean, event_based→mean, state→latest, duration→max.

**D14. Comparisons (V1 closed list).** 8 comparison types: `yesterday` (J-1), `same_weekday_last_week` (J-7), `rolling_avg` (window_days param, range 3-90), `rolling_min` (window_days), `rolling_max` (window_days), `target_value` (target param), `trend` (window_days, linear regression slope), `same_week_last_year` (requires ≥53 weeks of LTS; otherwise returns `insufficient_history`). User selects per field. Defaults: yesterday + same_weekday_last_week + rolling_avg(14) enabled.

**D15. Anomaly detection per field, three modes.** Per-field config (not global). Modes: `none`, `z_score` (sigmas param, default 2), `static_threshold` (min, max params), `pct_change_vs_rolling_avg` (pct, window_days params). Outputs alerts with severity `info | warning | critical`. User can override severity per field.

**D16. Storage via HA `Store` with FIFO rotation.** One file per instance: `.storage/morning_brief_<entry_id>`. Default rotation cap: 30 briefs. Configurable in options (range 5-365). Last-write-wins for concurrent writes. Schema versioned (current `version: 1`).

**D17. Single canonical JSON, multiple renderings.** The `ReportBuilder` produces ONE canonical JSON document (schema in Section 15). All consumers derive their output from this JSON: the sensor entity exposes it in attributes; the markdown fallback renders from it; the notification short renders from it; the Lovelace card consumes it. No alternate "source of truth" exists.

**D18. JSON size handling.** Sensor entity attributes are limited (~16KB in HA). If the canonical JSON exceeds 16KB: only meta + alerts + a `_truncated: true` flag are exposed in attributes. Full JSON is retrieved via service `morning_brief.get_last_brief`. Card detects `_truncated` and falls back to the service call.

**D19. Notification strategy: option B (manual user setup).** The integration does NOT auto-install Lovelace views or modify dashboards. It exposes the sensor entity; the user manually adds the card to their dashboard. The repo ships YAML templates in `docs/examples/`. Notifications have a configurable `clickAction` URL pointing wherever the user has placed the card.

**D20. Multilanguage rules.** Languages supported at launch: FR + EN. Architecture supports adding more languages by adding a JSON file in `translations/` (backend) and `src/i18n/` (frontend). Rules:
- No user-facing string hardcoded anywhere — backend or frontend
- Instance language auto-detected from `hass.config.language` at instance creation
- Override possible per instance
- Fallback EN
- A single label per user-defined field/category (in the instance language). Changing instance language does NOT translate user labels; user re-edits if desired
- Prompt template stays in English; the model is told `{{language}}` and replies in that language

**D21. Drag & drop: deferred to V2.** HA does not currently support native drag&drop on subentry lists. V1 implements a dedicated "Reorder" step in the options flow with ↑↓ buttons per item. When HA exposes native D&D, migrate.

**D22. AI credentials in `config_entry.data`.** Credentials (API keys) stored in `config_entry.data` (not `options`). Documented warning in README that these are stored unencrypted on disk per HA convention. Users can also use `secrets.yaml` references.

**D23. Event detection rules (CRITICAL).** For `event_based` and `duration` providers, "an event occurred" means: a state change happened where the new value is numerically different (epsilon configurable, default 0) from the previous valid value, AND the new value is not `unavailable` or `unknown`. Use `recorder.get_state_changes` not `last_updated`. Deduplicate consecutive identical numeric values. Apply optional `min_debounce` (default 5 minutes) to ignore rapid bouncing.

**D24. Same-week-last-year comparison.** Requires ≥53 weeks of LTS. If insufficient, return comparison with `status: insufficient_history` and `available_weeks: N`. Compares ISO week N current year vs ISO week N previous year. Aggregation matches the field's `weekly_aggregation` if running in a weekly report; otherwise uses `mean`.

**D25. File size limit.** No source file exceeds 300 lines without a `# rationale:` comment at the top justifying the exception. Aim for 100-200 lines as the typical size.

## Coding rules (NON-NEGOTIABLE)

**R1. No hardcoded user-facing strings.** All user-facing strings — error messages, labels, descriptions, UI text, log messages users may see — go through translation files. The ONLY exceptions: log messages strictly for developers (DEBUG/INFO level for diagnostic only), internal exception type names, and keys themselves.

**R2. File size cap.** No file exceeds 300 lines without a `# rationale: <reason>` comment at the top of the file. If you find yourself approaching 250 lines, refactor first.

**R3. Type hints everywhere.** Backend: Python 3.12+ syntax (`list[int]`, `dict[str, Any]`, `X | None`). No `Any` without justification. Run `mypy --strict` clean.

**R4. Docstrings.** Every module has a one-line docstring at the top. Every public class has a docstring. Every public function/method has a docstring (description + Args + Returns + Raises if applicable).

**R5. ABC inheritance.** Every provider, AI provider, logical-day strategy, report builder MUST inherit its ABC and pass `validate_config` successfully before instantiation. The factory rejects invalid configs.

**R6. No bare `except`.** Always catch the specific exception class. `except Exception` is allowed only at the top of an entry point (coordinator update loop, service call entry) to prevent total integration crash; the exception must be logged and the system put into a sane fallback state.

**R7. Index timeseries by date.** Any data structure representing a time-indexed series MUST be a dict `{date: value}`, never a list where position implies date. The recorder API returns lists; immediately convert.

**R8. Defensive against missing/invalid data.** Code that reads sensor states MUST handle: entity doesn't exist, state is `unavailable`, state is `unknown`, state is `None`, attribute is missing, attribute is wrong type. None of these propagate as crashes. Each handles with a sensible fallback (e.g., `value.stale=true`) and a log line.

**R9. Async I/O only.** No blocking I/O in the event loop. File I/O via `hass.async_add_executor_job` or `aiofiles`. HTTP via `aiohttp_client.async_get_clientsession`.

**R10. No long-running operations in setup.** `async_setup_entry` returns quickly. Long operations (initial data fetch) go in the coordinator's first refresh, which runs after setup.

**R11. Test coverage minimums.** ≥ 70% line coverage on: `providers/`, `history/`, `compute/`, `logical_day/`, `reports/canonical.py`.

**R12. No global mutable state.** All state lives on the coordinator instance or in HA storage. No module-level dicts that hold runtime data.

**R13. Translation files validity.** Every key added to one translation file MUST be added to all others (FR + EN at minimum).

**R14. Conventional commits.** All commits follow conventional commit format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `build:`, `ci:`.

**R15. Lint clean.** Backend: `ruff check` clean. CI fails on lint errors.

## Gotchas (READ BEFORE TOUCHING the relevant subsystem)

**G1. Event detection — DO NOT use `last_updated`.** Use `recorder.get_state_changes` over a recent window, filter out `unavailable`/`unknown` transitions, deduplicate consecutive identical numeric values (within epsilon). Applies to: `event_based`, `duration` providers.

**G2. LTS partial coverage is common.** Always check actual coverage of the requested window; never assume.

**G3. `recorder.get_statistics` does not return missing buckets.** INDEX BY DATE. Iterate over expected dates, look up in a dict.

**G4. Subentry type declaration.** `subentry_type` strings are declared via the integration manifest or class decorator. Instance creation is fully dynamic.

**G5. Availability gate ≠ provider type.** The gate is a separate concept attached to ANY provider. Implementing the gate logic inside individual providers is wrong — single `availability.py` module.

**G6. Logical day `cal_offset` matters.** After computing `(logical_date, cal_offset)`, downstream code uses BOTH. Don't drop `cal_offset`.

**G7. Recorder retention vs LTS retention.** Default recorder retention (short-term history) is 10 days. LTS is kept indefinitely (if state_class present). Users may have customized retention. Detect actual retention via the recorder config; do not hardcode 10.

**G8. `Store` write is async.** `store.async_save(data)` is async. Awaiting inside a tight loop is wrong; batch writes.

**G9. Translation file format is HA-specific.** Use HA's translation conventions (`config`, `options`, `services`, `entity`, `selector`, `exceptions` top-level keys). Validate against the HA developer docs at scaffold time.

**G10. Card never makes HTTP calls.** The card consumes data from `hass.states[entity_id]` only. For the >16KB fallback, the card calls the integration service via `hass.callService`. No direct HTTP. No fetch.

**G11. `hass.language` may be null.** On initial load or in some environments, `hass.language` can be undefined. Always default to `en` if null.

**G12. Lit reactive properties.** LitElement re-renders when reactive properties change. Always reassign: `this._data = {...this._data, key: newValue}`.

**G13. JSON >16KB → service fallback.** Implement this from the start, don't retrofit.

**G14. AI provider retry must be asynchronous.** The retry mechanism uses `asyncio.sleep` between attempts. Total time can be several minutes. The coordinator should NOT block.

**G15. Weekly week boundaries.** ISO week starts Monday. User-configurable `start_day_of_week`. When computing "current week" vs "previous week", use the configured start day, not the calendar default.

## Current status

- [x] Step 0: memory files created
- [x] Step 1: repo scaffolding
- [x] Phase 1: Foundation
  - [x] manifest.json
  - [x] const.py
  - [x] types.py
  - [x] exceptions.py
  - [x] translations/{en,fr}.json (skeleton)
  - [x] coordinator.py (skeleton)
  - [x] store.py (BriefStore with FIFO rotation)
  - [x] __init__.py (setup_entry, unload_entry, remove_entry)
  - [x] tests/test_store.py
- [x] Phase 2: History layer
  - [x] history/lts.py — daily LTS via recorder.statistics_during_period
  - [x] history/short_term.py — state_changes_during_period + per-day aggregator
  - [x] history/event_detector.py — filter unavailable/unknown + epsilon dedup + debounce (G1, D23)
  - [x] history/hybrid.py — LTS-first, short-term gap-fill bounded by recorder retention (G7), D11 status enum
  - [x] history/__init__.py — public exports
- [x] Phase 3: Providers
  - [x] providers/base.py — FieldProvider ABC
  - [x] providers/__init__.py — registry + create_provider/detect_provider factory
  - [x] providers/instantaneous.py + tests
  - [x] providers/cumulative.py + tests
  - [x] providers/manual.py + tests
  - [x] providers/state.py + tests
  - [x] providers/event_based.py + tests
  - [x] providers/duration.py + tests
  - [x] providers/calendar.py + tests
  - [x] providers/weather.py + tests (rationale: composite + dual-format)
- [x] Phase 4: Logical day & triggers
  - [x] logical_day/base.py — LogicalDayStrategy ABC
  - [x] logical_day/{fixed_cutoff,sleep_sensor,manual}.py — 3 strategies (D6)
  - [x] logical_day/__init__.py — STRATEGIES registry + create_strategy
  - [x] triggers/schedule.py — cron-style time trigger
  - [x] triggers/sensor_based.py — state-machine: trigger→delay→optout-shortcut, daily fallback (rationale: 3 listeners + 5-state machine kept cohesive)
  - [x] triggers/__init__.py
- [x] Phase 5: Availability gate & comparisons & anomaly
  - [x] compute/availability.py — apply_gate (D5, G5)
  - [x] compute/comparisons.py — 8 V1 types + dispatcher + interpretation (D14, rationale)
  - [x] compute/anomaly.py — 3 detection modes + dispatcher (D15)
  - [x] compute/__init__.py
- [x] Phase 6: AI layer
  - [x] ai/base.py — AIProvider ABC
  - [x] ai/disabled.py — empty-envelope degraded mode (D9)
  - [x] ai/ha_ai_task.py — wraps ai_task.* HA entities
  - [x] ai/anthropic_direct.py — direct api.anthropic.com via aiohttp
  - [x] ai/openai_direct.py — direct api.openai.com via aiohttp
  - [x] ai/retry.py — 3-attempt exponential back-off + JSON validation (D8, G14)
  - [x] ai/prompt_template.py — Jinja2 loader with StrictUndefined
  - [x] ai/__init__.py — AI_PROVIDERS registry + create_ai_provider factory
  - [x] prompts/{morning,evening,weekly}_v1.txt — English templates with {{ language }} directive
- [x] Phase 7: Reports & canonical JSON
  - [x] reports/base.py — ReportBuilder ABC + shared `_resolve_field` pipeline (rationale: shared with formatters)
  - [x] reports/canonical.py — `build_canonical_json` (Sections 14.5 + 15)
  - [x] reports/morning.py — flagship, full AI pipeline + degraded fallback
  - [x] reports/evening.py — composes on morning, forces cal_offset=0
  - [x] reports/weekly.py — ISO-week aggregation per `weekly_aggregation` (D13, G15)
  - [x] reports/__init__.py — REPORTS registry + create_report
  - [x] rendering/markdown.py — Section 28 fallback view
  - [x] rendering/notification_short.py — Section 27 3-line mobile body
- [x] Phase 8: Config flow & subentries
  - [x] config_flow.py — 6-step initial flow (rationale: shared `_draft` state across steps)
  - [x] options_flow/* — 8 sections + per-section schemas
  - [x] subentries/field/ (7 steps) + subentries/category/ (1 step)
  - [x] Translations populated EN+FR (133 keys, parity validated)
- [x] Phase 9: Services, entities, events
  - [x] coordinator.py — async_generate_brief / async_preview_brief, fires `morning_brief_generated` + `morning_brief_ai_failed`
  - [x] services.py + services.yaml — 8 services (Section 18.2)
  - [x] sensor.py — main + status sensors with D18/G13 truncation
  - [x] button.py — generate + preview
  - [x] __init__.py — full wiring (platforms forward + services register + subentry collection)
  - [x] test_e2e_morning.py — config entry setup, generate, preview, get_last_brief, unload, truncation
- [x] Phase 10: Frontend card (lives in `morning-brief-card`)
- [x] Phase 11: Docs & blueprints & examples
- [ ] Phase 12: Polish & release prep

## Open questions / blockers

- **Brand icons are still placeholders.** `custom_components/morning_brief/brand/{icon,dark_icon,icon@2x,dark_icon@2x}.png` are fully-transparent 256/512 RGBA PNGs. User to replace with real artwork before v1.0.0 (Phase 12). HACS Validate accepts the placeholders.
- **`docs/img/preview.png` is a placeholder.** Referenced from README — needs a real screenshot of the card rendering a sample brief, captured during Phase 12 against a live HA.
- **No manual end-to-end test against a real running HA.** All 299 tests are pytest-homeassistant-custom-component-based with mocked recorder/AI. Phase 12 should include a sanity install via HACS into a real HA instance to verify config_flow UX, subentry flow, service responses, and the `_truncated` fallback on a real >16 KB brief.
- **`MORNING_BRIEF_SPEC.md` is committed (136 KB) at the repo root.** It's nice for offline reference but bloats the HACS repo. Decision to keep or drop before v1.0.0 — currently kept.

CI status on `machintrucbidule/ha-morning-brief` (after Phase 11 push `e413c7b`):
- ✅ Tests (pytest, 299 passed, 0 skipped — full integration test suite)
- ✅ Lint (ruff + mypy --strict)
- ✅ HACS Validate (8/8 checks, brands satisfied via placeholders)

## Session log

- 2026-05-15 — Read MORNING_BRIEF_SPEC.md in full (all 43 sections). Created memory files (CLAUDE.md, DECISIONS.md, PROGRESS.md) for both repos. Scaffolded the integration repo file tree (Section 3.1) and the frontend repo file tree (Section 3.2) with stubs and `.gitkeep` placeholders. Implemented Phase 1 (Foundation) of Section 36: `manifest.json`, `const.py` (all enums/defaults), `types.py` (dataclasses + TypedDicts mirroring Section 15), `exceptions.py`, `translations/{en,fr}.json` skeleton (HA-conventional keys, key parity validated), `coordinator.py` skeleton (DataUpdateCoordinator, event-driven — no polling), `store.py` with FIFO rotation + retention clamp + remove, `__init__.py` (async_setup_entry / async_unload_entry / async_remove_entry), and `tests/test_store.py` covering rotation, ordering, retention clamp, get-by-uuid, clear, async_remove. Ruff clean on every file; JSON valid; translation EN/FR key parity OK.
- 2026-05-15 — Initialized two git repos and pushed: `home-assistant-morning-brief` → https://github.com/machintrucbidule/ha-morning-brief (2 commits: `chore: bootstrap memory files and repo scaffolding`, `feat: foundation skeleton`); `morning-brief-card` → originally https://github.com/machintrucbidule/-ha-morning-brief-card, renamed by user to https://github.com/machintrucbidule/ha-morning-brief-card. Local git user.email set to `ivan.calmels@gmail.com` per-repo. Triggered first CI run; iterated 2 fix commits to get Tests + Lint green: `fix(ci): pytest-asyncio auto mode, mypy cast, hacs country` (created pyproject.toml with `asyncio_mode = "auto"`, dropped a redundant `cast` in `store.py`, **incorrectly** removed `'EN'` from `country` in both hacs.json files), then `fix(tests): respect MIN_RETENTION=5 in rotation tests`. Topics added to both repos via `gh repo edit`.
- 2026-05-15 — User feedback caught a real spec violation: I had conflated HACS geography (`country` field, ISO 3166-1) with project language support (D20: EN + FR). Corrected: `hacs.json` `country` now `["FR", "US", "GB"]` (geography for both language audiences). Spec language support was always intact in code (`SUPPORTED_LANGUAGES`, `translations/{en,fr}.json`) — only the marketing/discovery metadata was wrong. Memory saved: `feedback_hacs_country_vs_language.md`. Also: added transparent placeholder brand icons (`custom_components/morning_brief/brand/{icon,dark_icon,icon@2x,dark_icon@2x}.png`) per user's choice — user will replace with real artwork before v1.0.0. Updated card-repo remote URL after user renamed `-ha-morning-brief-card` → `ha-morning-brief-card`.
- 2026-05-15 — Phase 2 (History layer) shipped. Implemented `history/lts.py` (LTS daily wrapper, date-indexed dict per G3), `history/short_term.py` (state_changes + per-day aggregator, `last_changed` only per G1), `history/event_detector.py` (pure-function pipeline: reject unavailable/unknown, epsilon dedup, debounce-keep-first per D23), `history/hybrid.py` (LTS-first orchestrator with short-term gap-fill bounded by recorder `keep_days` per G7, D11 status enum, D10 LTS-wins-on-conflict), `history/__init__.py` (public exports). 39 tests covering Section 10.7 scenarios (LTS-only, short-term-only, mixed, conflicts, gap status enum, retention lookup). Two follow-up commits fixed mypy strict warnings only visible on CI: `get_instance` import requires `# type: ignore[attr-defined]` (HA doesn't export it via `__all__` anywhere); `statistics_during_period` rows are `StatisticsRow` TypedDict — explicit `cast()` for the loop type. Final state on `5e2007e`: ✅ Tests (56 passed, 22 skipped) ✅ Lint (ruff + mypy --strict) ✅ HACS Validate (8/8).
- 2026-05-15 — Phase 3 (Providers) shipped as a single cohesive commit (per-provider commits would have left intermediate states broken because the registry imports all 8 classes). `providers/base.py` ABC + `providers/__init__.py` registry with create_provider/detect_provider factory. All 8 V1 providers (Section 8): instantaneous, cumulative, manual, state, event_based, duration, calendar, weather (latter two with `# rationale:` headers). Each has config schema, `validate_config`, `detect_from_entity` heuristic. ~80 tests. Two follow-up commits fixed CI: `patch(hass.services, "async_call")` is forbidden (ServiceRegistry attr is read-only) — patch `ServiceRegistry.async_call` at class level instead; mypy strict required `dict[str, Any]` type-args on `create_provider` and a default-empty for the `Optional[str]` attribute_name in duration. Final state on `dfea2ab`: ✅ Tests (144 passed, 14 skipped) ✅ Lint ✅ HACS.
- 2026-05-15 — Phase 4 (Logical day strategies + triggers) shipped in one commit. `logical_day/base.py` ABC + `logical_day/__init__.py` registry. Three strategies (D6): `fixed_cutoff` (default hour-based), `sleep_sensor` (recorder-driven wake detection with nap filter + hard fallback), `manual` (in-memory advance via `advance_day` method — Phase 9 wires to service; persistence across HA restart is a noted V1 limitation). Two triggers (D7): `ScheduleTrigger` (cron-style HH:MM + days_of_week) and `SensorBasedTrigger` (trigger→delay→opt-out shortcut, daily fallback; `# rationale:` header for the 5-state machine + 3 listeners). Both swallow callback exceptions at the entry-point boundary (R6). Tests: 41 new cases. Two follow-up CI fixes: my sleep_sensor test expectations were wrong (the `(wake - 4h)` anchor lands on TODAY for typical wakes; only pre-04:00 wakes anchor to yesterday — implementation was correct, tests were); mypy strict required `Event[EventStateChangedData]` (not generic `Event`) on the listener parameters since `async_track_state_change_event` specialises the generic. Final state on `c45c418`: ✅ Tests (186 passed, 11 skipped) ✅ Lint ✅ HACS.
- 2026-05-15 — Phase 5 (Availability gate + comparisons + anomaly) shipped in one commit. `compute/availability.py` (`apply_gate`, transverse/provider-agnostic per D5/G5 — fallback to previous day on gate miss or gate-sensor unavailable; gate is never inside a provider). `compute/comparisons.py` (rationale: all 8 V1 types kept cohesive — yesterday, same_weekday_last_week, rolling_avg/min/max, target_value, trend with collinear-x guard, same_week_last_year with the 365-day LTS check from D24 — plus `compute_interpretation` helper and `evaluate_comparisons` dispatcher that wraps each compare in try/except per R6 entry-point rule). `compute/anomaly.py` (3 detection modes + `none` no-op: z_score with severity buckets ≥3σ critical / ≥2σ warning, static_threshold with configurable per-side severity, pct_change_vs_rolling_avg with zero-mean guard). 43 new tests. One follow-up CI fix: mypy strict refused the heterogeneous `_WEEKLY_AGG_REDUCERS` dict — added an explicit `Callable[[list[float]], float]` typedef and wrapped `sum`/`max`/`min` so all reducers share that signature. Final state on `a2f3fd4`: ✅ Tests (229 passed, 8 skipped) ✅ Lint ✅ HACS.
- 2026-05-15 — Phase 6 (AI layer) shipped in one commit, green on first push (no CI rework). `ai/base.py` AIProvider ABC + 4 implementations (D8): `disabled` (empty-envelope degraded mode for D9), `ha_ai_task` (wraps any `ai_task.*` HA entity via the `ai_task.generate_data` service), `anthropic_direct` (POST to api.anthropic.com/v1/messages via HA's shared aiohttp), `openai_direct` (POST to api.openai.com/v1/chat/completions). All four convert exceptions / non-200 to `AIResult(status=error)` per D9. `ai/retry.py` wraps any provider with `generate_with_retry`: 3 attempts, exponential back-off (60s/120s/240s defaults), JSON validation — uses `asyncio.sleep` so the coordinator can interleave work (G14). `ai/prompt_template.py`: Jinja2 loader with `StrictUndefined` (typos fail loudly) + executor-loaded `from_file` (R9) + `for_report_type` resolver. `prompts/{morning,evening,weekly}_v1.txt`: English templates with `{{ language }}` directive so the model replies in the target language (D20). ~50 new tests including aiohttp session mocking via fake async-context-manager. Final state on `2f66855`: ✅ Tests (265 passed, 6 skipped) ✅ Lint ✅ HACS.
- 2026-05-15 — Phase 7 (Report builders + renderings) shipped in one commit. `reports/base.py` (rationale) — `ReportBuilder` ABC plus the shared `_resolve_field` orchestration pipeline (provider → gate → comparisons → anomaly → sparkline) + format helpers. `reports/canonical.py` — `build_canonical_json` produces Section 15 dict byte-for-byte (categories grouped/sorted with empty-drop, anomaly+AI alerts merged). `reports/morning.py` — flagship: filters `visible_in:morning`, runs the AI pipeline, three `ai_status` paths (ok / disabled / degraded). `reports/evening.py` — composes on Morning with `visible_in:evening` and forces `cal_offset=0`. `reports/weekly.py` — distinct pipeline: ISO-week aggregation per `weekly_aggregation` (D13), `change` agg for cumulative sensors, comparison set narrowed to target_value + same_week_last_year. `rendering/markdown.py` + `rendering/notification_short.py` per Sections 27/28. ~20 new tests covering canonical structure + e2e morning/evening/weekly with mocked compute+history layers (helper `patched_resolve_pipeline` context manager). Two follow-up CI fixes: a function-local `evaluate_comparisons` import in weekly.py made `patch()` blind — hoisted to module level; mypy strict required typed locals on `template.render()` returns to keep `-> str` happy. Final state on `a44b594`: ✅ Tests (286 passed, 2 skipped) ✅ Lint ✅ HACS.
- 2026-05-15 — Phase 8 (Config flow + options + subentries) shipped. `config_flow.py` (rationale) — 6-step linear flow that accumulates a `_draft` dict and creates the entry on the final step. `options_flow/` — main menu + 8 sections (general, logical_day, trigger, notification, persistence, reorder_fields/categories, advanced) consolidated in one class with per-section schema files. `subentries/field/` (7 steps) + `subentries/category/` (1 step) with `ConfigSubentryFlow` base, behind a `TYPE_CHECKING` shim that falls back to `ConfigFlow` if the HA version doesn't expose `ConfigSubentryFlow`. Translations EN+FR populated to 133 keys with parity validated (R13). 6 new tests. Four follow-up CI fixes: `ConfigSubentryFlow` not on old HA → defensive getattr; `recorder` was in `dependencies` (hard) blocking test setup → moved to `after_dependencies`; voluptuous sub-schemas rejecting extra keys from the union form → `extra=vol.REMOVE_EXTRA`; mypy strict wanted `ConfigFlowResult` (not `FlowResult`) on every flow step + `TYPE_CHECKING`-pinned base class to resolve subentry inheritance. Final state on `7879a85`: ✅ Tests (292 passed, 1 skipped) ✅ Lint ✅ HACS.
- 2026-05-15 — Phase 9 (Services + entities + events) shipped. Coordinator extended with `async_generate_brief` / `async_preview_brief` (full pipeline: logical_day strategy → ReportBuilder → BriefStore → bus events `morning_brief_generated` + `morning_brief_ai_failed` → push via `async_set_updated_data` for sensors). 8 services registered globally per Section 18.2 with HA descriptors in `services.yaml`. Sensor platform: main sensor exposing the canonical JSON with D18/G13 truncation past 16 KB; lightweight status sensor with meta fields. Button platform: generate (force=True) + preview. `__init__.py` builds the logical-day strategy, AI provider, prompt template, splits subentries into fields+categories, forwards setup to `sensor` + `button` platforms, registers services. `tests/test_e2e_morning.py` covers setup-creates-entities, generate-fires-event+persists, preview-doesn't-persist, get_last_brief, unload-drops-coordinator, plus unit tests on `_truncate_attributes`. Two follow-up CI fixes: `_async_update_data` was wired to `async_generate_brief` which auto-generated at setup time (broke D7 + preview test) — restored to load-from-store, generation is event-driven only; mypy strict needed an explicit `dict[str, Any]` annotation on the `entry.options` fallback in `_attach_options`. Final state on `5d93095`: ✅ Tests (299 passed, 0 skipped) ✅ Lint ✅ HACS.
- 2026-05-15 — Phase 11 (Docs + blueprints + examples) shipped for the integration repo. Written via standalone Python writer scripts (`write_docs.py` for the 5 docs, then `write_phase11.py` for everything else) because bash heredocs wrapped in `bash -c '...'` choke on apostrophes inside markdown bodies on Windows. README rewritten to the full Section 31 20-section structure (overview / features / requirements / install / quickstart / concepts / config overview / AI providers / field providers / comparisons / anomalies / triggers / services / events / entities / card link / multilanguage / troubleshooting / development / license). `docs/architecture.md` got the data-flow ASCII diagram + subsystem map + canonical-JSON / D17 / D1 callouts. `docs/providers.md` got the 8-provider decision tree table + availability-gate primer. `docs/triggers.md` covered the 3 levels + how to import the blueprints. `docs/ai_providers.md` documented the 4 backends + retry policy + a rough cost table. `docs/multilanguage.md` explained where strings live and how to add a language. 4 example YAMLs: `lovelace_basic.yaml`, `lovelace_compact.yaml`, `automation_level3_external_trigger.yaml`, `full_config_export.yaml`. 2 blueprints: `trigger_on_schedule.yaml` (L1 — `config_entry` + `time` + `weekday` selectors, `force` toggle), `trigger_on_wake.yaml` (L2 — wake sensor + delay + opt-out list + hard fallback time, `mode: restart`). CHANGELOG.md and info.md finalised. No code changes outside docs/blueprints/yaml. CI after push `e413c7b`: ✅ Tests (299 passed, 0 skipped) ✅ Lint ✅ HACS Validate.
- 2026-05-15 — End-of-session ritual review (post-Phase-11). The first pass of the Phase 11 ritual missed steps 3 (Open questions / blockers refresh) and partially fumbled step 9 (summary switched to English after a context compression, instead of staying in the French we had been speaking). Also referenced a `feedback_bash_heredoc_apostrophes.md` memory I had not actually written. Corrected: refreshed the blockers section in both CLAUDE.md to reflect post-Phase-11 reality (placeholder brand icons + placeholder preview screenshot + no live HA install test yet + committed-spec decision), re-ordered the card CLAUDE.md session log chronologically (Phase 11 entry now after Phase 10), and created the missing memory file `feedback_bash_heredoc_apostrophes.md`. Lesson — apply the ritual right after the implementation push, before any context-compression event.
