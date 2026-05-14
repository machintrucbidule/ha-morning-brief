# Morning Brief — Complete Implementation Specification

> This document is the exhaustive specification for the `morning-brief` Home Assistant integration and its companion Lovelace card. It is the single source of truth for implementation. Read fully before writing any code.

---

## 0. How to use this document

This is your implementation contract. The workflow is:

1. **Read this entire document first** before writing any code.
2. **Execute Section 2 (memory files)** before anything else — these files are how future sessions stay aligned with the spec.
3. **Execute Section 3 (repo scaffolding)** to create the file tree.
4. **Then follow Section 36 (implementation plan)** phase by phase.
5. **At the end of every session**, execute Section 38 (end-of-session ritual).

This document is **immutable** unless the user explicitly authorizes a change, which must be logged in `DECISIONS.md` with rationale.

If anything in this document is ambiguous or contradicts itself, **stop and ask the user**. Do not infer or invent.

---

## 1. Project mission and context

### What we are building

Two HACS-public repositories distributed independently:

1. **`home-assistant-morning-brief`** — a Python custom_component for Home Assistant that:
   - Reads user-configured sensors (with 8 different reading strategies depending on sensor type)
   - Computes comparisons against historical data (yesterday, last week, rolling averages, year-over-year, etc.)
   - Detects anomalies per field
   - Sends the structured data to an AI model for narrative enrichment (insights, weather synthesis, verdict)
   - Produces a canonical JSON document representing the brief
   - Persists the last N briefs (default 30) with FIFO rotation
   - Notifies the user via their chosen notification service
   - Exposes the data via a sensor entity for Lovelace consumption

2. **`morning-brief-card`** — a TypeScript/Lit Lovelace custom card that:
   - Renders the canonical JSON produced by the integration
   - Allows navigation through historical briefs (< >)
   - Is fully configurable via the standard Lovelace card editor GUI

### Target audience

Home Assistant power users who want a single, daily, AI-narrated dashboard of their personal metrics (health, home, weather, calendar, custom data) without locking into a specific sensor brand or vendor ecosystem.

### Why this matters

This integration replaces ad-hoc YAML automations with a maintainable, configurable, generic, multi-vendor product. It must work for users with completely different sensor setups — health trackers (Garmin/Fitbit/Apple/Amazfit/etc.), energy meters (Linky/Shelly/IoTaWatt), weather providers (Open-Meteo/Met.no/etc.), and so on.

### Core principles

1. **Generic, not bespoke.** The integration must not hardcode any specific sensor brand, name, or behavior.
2. **Configurable by GUI.** Users should be able to do 95% of configuration via the HA config flow GUI, with YAML examples available for the remaining 5%.
3. **Multi-language ready.** FR and EN at launch; structure supports adding more.
4. **Robust by default.** Missing entities, unavailable values, stale data, AI failures — none of these should produce a crash or a broken brief.
5. **Reliable on data.** Sensor reset behaviors (around midnight, conditional validity, heartbeats) are handled correctly out of the box.
6. **Small, modular, evolvable.** No giant files. Each subsystem isolated.
7. **One canonical JSON, multiple renderings.** The integration produces JSON; the card, notification, and markdown fallback are independent consumers.

---

## 2. STEP 0 — Memory files (DO THIS FIRST)

Before writing any code, create three memory files in each of the two repos. These files are your persistent memory across sessions.

### 2.1 `CLAUDE.md` (one in each repo root)

This file is loaded at the start of every Claude Code session. It is the project's running state.

**Template for the integration repo (`home-assistant-morning-brief/CLAUDE.md`):**

```
# CLAUDE.md — home-assistant-morning-brief

## Read this first, every session

This file is your persistent memory. Read it at the start of every session BEFORE doing anything else. Update the "Current status", "Open questions", and "Session log" sections at the END of every session.

The full specification lives in MORNING_BRIEF_SPEC.md (committed at the project root next to this file). When in doubt about ANY behavior, refer to the spec. Do not infer.

## Project context

Python custom_component for Home Assistant. Generates configurable AI-enriched daily/evening/weekly briefs from user-defined sensors. HACS-public. Companion frontend lives in the sibling repo `morning-brief-card`.

## Architecture decisions (IMMUTABLE — do not change without user approval logged in DECISIONS.md)

[Copy decisions D1-D25 from Section 4 of MORNING_BRIEF_SPEC.md verbatim here at first session creation.]

## Coding rules (NON-NEGOTIABLE)

[Copy rules R1-R15 from Section 5 of MORNING_BRIEF_SPEC.md verbatim here at first session creation.]

## Gotchas (READ BEFORE TOUCHING the relevant subsystem)

[Copy gotchas G1-G15 from Section 6 of MORNING_BRIEF_SPEC.md verbatim here at first session creation.]

## Current status

[Updated at the end of every session. Format:]

- [x] Step 0: memory files created
- [x] Step 1: repo scaffolding
- [ ] Phase 1: Foundation
  - [x] manifest.json
  - [x] const.py
  - [ ] coordinator.py
  - ...

## Open questions / blockers

[Anything unresolved or requiring user input. Empty if none.]

## Session log

[Append-only log of what was done in each session.]

- 2026-MM-DD — Created memory files. Scaffolded integration manifest. Implemented X.
- 2026-MM-DD — ...
```

**Template for the frontend repo (`morning-brief-card/CLAUDE.md`):**

Same structure, adapted:

```
# CLAUDE.md — morning-brief-card

## Read this first, every session

[same intro]

## Project context

TypeScript/Lit Lovelace custom card for Home Assistant. Consumes the canonical JSON produced by the `home-assistant-morning-brief` integration. HACS-public. Standalone repo but tightly coupled to the integration's JSON schema (see Section 15 of MORNING_BRIEF_SPEC.md).

## Architecture decisions (IMMUTABLE)

[Same decisions D1-D25, adapted to frontend perspective where relevant.]

## Coding rules (NON-NEGOTIABLE)

[Same rules R1-R15, plus frontend-specific:]
- F1. Strict TypeScript. No `any`.
- F2. No HTTP calls from the card. All data comes from `hass.states[entity_id]`.
- F3. All strings via `src/i18n/<lang>.json`. Loader picks language based on `hass.language`. Fallback EN.
- F4. Use LitElement, not React or other frameworks.
- F5. Use Lit's `ifDefined`, `repeat`, etc. — no manual DOM manipulation.

## Gotchas

[Same gotchas, plus frontend-specific:]
- FG1. The card receives JSON > 16KB cap via service `morning_brief.get_last_brief` not via entity attributes. Detect by inspecting `value._truncated` flag.
- FG2. `hass.language` may be `null` during initial load. Always fallback gracefully.

## Current status / Open questions / Session log

[Same as integration repo.]
```

### 2.2 `DECISIONS.md` (one in each repo root)

Append-only log. Any architectural change requires an entry. Format:

```
# DECISIONS.md

## YYYY-MM-DD — <short title>

**Context**: <why this came up>
**Decision**: <what was decided>
**Consequence**: <impact on code, tests, docs>
**Approved by**: <user explicit / assumed from spec>

---

## 2026-XX-XX — Initial spec lock

**Context**: Project kickoff. The spec was produced collaboratively by the user and a planning AI session.
**Decision**: Lock all architecture decisions D1-D25 as defined in MORNING_BRIEF_SPEC.md Section 4.
**Consequence**: Implementation must follow these decisions strictly. Any deviation requires a new entry.
**Approved by**: User (initial project setup)
```

### 2.3 `PROGRESS.md` (one in each repo root)

Live checklist. Updated continuously. Format:

```
# PROGRESS.md

## Phase 1 — Foundation
- [ ] manifest.json (HA Core min version, dependencies, subentry types declared)
- [ ] const.py (DOMAIN, defaults, enums)
- [ ] types.py (TypedDicts, dataclasses)
- [ ] exceptions.py
- [ ] translations/{en,fr}.json (skeleton)
- [ ] coordinator.py (DataUpdateCoordinator subclass)
- [ ] store.py (HA Store wrapper, FIFO rotation)
- [ ] __init__.py (setup_entry, unload_entry)
- [ ] Tests: store rotation

## Phase 2 — History layer
- [ ] history/lts.py
- [ ] history/short_term.py
- [ ] history/event_detector.py
- [ ] history/hybrid.py
- [ ] Tests: LTS only, short-term only, mix, gaps, conflicts

[... continue for all 12 phases, see Section 36 of spec ...]
```

### 2.4 Session ritual

At the **start** of every session:
1. Read `CLAUDE.md`
2. Read `PROGRESS.md`
3. Read `DECISIONS.md`
4. Summarize state to the user to confirm context loaded
5. Ask what to work on (or continue the next pending item)

At the **end** of every session:
1. Update `PROGRESS.md` checkboxes
2. Append entry to `Session log` in `CLAUDE.md`
3. Update `Open questions / blockers` in `CLAUDE.md`
4. If any decision was made/changed: append to `DECISIONS.md`
5. Run tests for what you touched; commit only green
6. Commit with conventional commit format (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)

---

## 3. STEP 1 — Repo scaffolding

After memory files are created, scaffold the file trees for both repos.

### 3.1 Integration repo file tree

```
home-assistant-morning-brief/
├── CLAUDE.md
├── DECISIONS.md
├── PROGRESS.md
├── MORNING_BRIEF_SPEC.md           # This document, committed
├── README.md                       # English, comprehensive (Section 31)
├── CHANGELOG.md                    # Keep-a-Changelog format
├── info.md                         # Short HACS description
├── hacs.json                       # type: integration
├── LICENSE                         # MIT (or user-chosen)
├── .gitignore
├── .github/
│   └── workflows/
│       ├── hacs-validate.yml
│       ├── lint.yml
│       └── test.yml
├── docs/
│   ├── providers.md
│   ├── triggers.md
│   ├── ai_providers.md
│   ├── multilanguage.md
│   ├── architecture.md
│   ├── img/                        # screenshots placeholders
│   │   └── .gitkeep
│   └── examples/
│       ├── lovelace_basic.yaml
│       ├── lovelace_compact.yaml
│       ├── automation_level3_external_trigger.yaml
│       └── full_config_export.yaml
├── blueprints/
│   └── automation/
│       └── morning_brief/
│           ├── trigger_on_wake.yaml
│           └── trigger_on_schedule.yaml
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sensor_states.json
│   │   └── lts_data.json
│   ├── providers/
│   │   ├── test_cumulative.py
│   │   ├── test_instantaneous.py
│   │   ├── test_event_based.py
│   │   ├── test_state.py
│   │   ├── test_duration.py
│   │   ├── test_calendar.py
│   │   ├── test_weather.py
│   │   └── test_manual.py
│   ├── history/
│   │   ├── test_lts.py
│   │   ├── test_short_term.py
│   │   ├── test_event_detector.py
│   │   └── test_hybrid.py
│   ├── compute/
│   │   ├── test_comparisons.py
│   │   ├── test_anomaly.py
│   │   └── test_availability.py
│   ├── logical_day/
│   │   ├── test_fixed_cutoff.py
│   │   ├── test_sleep_sensor.py
│   │   └── test_manual.py
│   ├── ai/
│   │   ├── test_retry.py
│   │   └── test_disabled.py
│   ├── reports/
│   │   ├── test_morning.py
│   │   ├── test_evening.py
│   │   ├── test_weekly.py
│   │   └── test_canonical.py
│   ├── test_store.py
│   ├── test_config_flow.py
│   └── test_e2e_morning.py
└── custom_components/
    └── morning_brief/
        ├── __init__.py
        ├── manifest.json
        ├── const.py
        ├── types.py
        ├── exceptions.py
        ├── coordinator.py
        ├── store.py
        ├── sensor.py
        ├── button.py
        ├── services.py
        ├── services.yaml
        ├── translations/
        │   ├── en.json
        │   └── fr.json
        ├── config_flow.py
        ├── options_flow/
        │   ├── __init__.py
        │   ├── general.py
        │   ├── logical_day.py
        │   ├── trigger.py
        │   ├── ai.py
        │   ├── notification.py
        │   ├── persistence.py
        │   ├── reorder.py
        │   └── advanced.py
        ├── subentries/
        │   ├── __init__.py
        │   ├── field/
        │   │   ├── __init__.py
        │   │   ├── flow.py
        │   │   └── schema.py
        │   └── category/
        │       ├── __init__.py
        │       └── flow.py
        ├── providers/
        │   ├── __init__.py            # registry + factory
        │   ├── base.py
        │   ├── cumulative.py
        │   ├── instantaneous.py
        │   ├── event_based.py
        │   ├── state.py
        │   ├── duration.py
        │   ├── calendar.py
        │   ├── weather.py
        │   └── manual.py
        ├── history/
        │   ├── __init__.py
        │   ├── lts.py
        │   ├── short_term.py
        │   ├── hybrid.py
        │   └── event_detector.py
        ├── compute/
        │   ├── __init__.py
        │   ├── comparisons.py
        │   ├── anomaly.py
        │   └── availability.py
        ├── logical_day/
        │   ├── __init__.py            # registry
        │   ├── base.py
        │   ├── fixed_cutoff.py
        │   ├── sleep_sensor.py
        │   └── manual.py
        ├── triggers/
        │   ├── __init__.py
        │   ├── schedule.py
        │   └── sensor_based.py
        ├── ai/
        │   ├── __init__.py            # registry
        │   ├── base.py
        │   ├── ha_ai_task.py
        │   ├── anthropic_direct.py
        │   ├── openai_direct.py
        │   ├── disabled.py
        │   ├── retry.py
        │   └── prompt_template.py
        ├── reports/
        │   ├── __init__.py            # registry
        │   ├── base.py
        │   ├── morning.py
        │   ├── evening.py
        │   ├── weekly.py
        │   └── canonical.py
        ├── rendering/
        │   ├── __init__.py
        │   ├── markdown.py
        │   └── notification_short.py
        └── prompts/
            ├── morning_v1.txt
            ├── evening_v1.txt
            └── weekly_v1.txt
```

### 3.2 Frontend repo file tree

```
morning-brief-card/
├── CLAUDE.md
├── DECISIONS.md
├── PROGRESS.md
├── README.md
├── CHANGELOG.md
├── hacs.json                       # type: plugin
├── package.json
├── tsconfig.json
├── rollup.config.js
├── .eslintrc.json
├── .prettierrc
├── .gitignore
├── LICENSE
├── .github/
│   └── workflows/
│       ├── hacs-validate.yml
│       └── lint-build.yml
├── src/
│   ├── index.ts                    # entry, customElements.define
│   ├── card.ts                     # MorningBriefCard (LitElement)
│   ├── editor.ts                   # MorningBriefCardEditor
│   ├── types.ts                    # mirrors backend canonical JSON
│   ├── constants.ts
│   ├── i18n/
│   │   ├── index.ts                # loader
│   │   ├── en.json
│   │   └── fr.json
│   ├── components/
│   │   ├── header.ts
│   │   ├── alerts.ts
│   │   ├── category.ts
│   │   ├── field.ts
│   │   ├── sparkline.ts
│   │   ├── weather.ts
│   │   ├── verdict.ts
│   │   └── footer.ts
│   ├── styles/
│   │   ├── card.css.ts
│   │   └── editor.css.ts
│   └── utils/
│       ├── format.ts               # numbers, durations, locale-aware
│       ├── colors.ts               # direction_preference → color mapping
│       ├── history.ts              # navigation between stored briefs
│       └── data.ts                 # parsing, truncation detection
├── tests/
│   ├── card.test.ts
│   ├── format.test.ts
│   └── history.test.ts
├── dist/
│   └── .gitkeep                    # bundle output goes here
└── docs/
    ├── img/
    │   └── .gitkeep
    └── examples/
        ├── basic.yaml
        └── compact.yaml
```

---

## 4. Architecture decisions (IMMUTABLE)

These decisions are locked. Any change requires explicit user approval and a logged entry in `DECISIONS.md`.

**D1. HACS public distribution, two separate repos.**
The integration and the card are distributed as independent HACS repositories. They share a contract (the canonical JSON schema, Section 15) but have independent versioning and release cycles. Cross-references in READMEs.

**D2. HA Core minimum version.**
Target the latest stable HA Core version that supports BOTH `config_entries.subentries` AND `ai_task` component. Verify at scaffold time, document in `manifest.json`.

**D3. Subentries architecture for dynamic configuration.**
The integration declares 2 subentry types: `field` and `category`. Each has its own flow handler. Instances of subentries (= configured fields, created categories) are dynamic, added/edited/deleted by the user via the HA UI. The native HA UI handles add/edit/delete lifecycle.

**D4. 8 field provider types (V1 closed list).**
The closed V1 list is: `cumulative`, `instantaneous`, `event_based`, `state`, `duration`, `calendar`, `weather`, `manual`. Adding a new provider type in V2 requires a new file in `providers/` and registration in the factory — no other changes.

**D5. Availability gate is orthogonal.**
Every provider type supports an optional `availability_gate` config: `{entity_id, expected_state}`. When the gate is not satisfied at evaluation time, the provider returns the previous valid day's value with `stale: true, stale_reason: "awaiting_availability"`. The gate is NOT a provider type — it's a transverse feature.

**D6. Three logical-day strategies.**
`fixed_cutoff` (parameter: cutoff_hour, default 04:00), `sleep_sensor` (parameters: sensor binary_sensor, awake_state, hard_fallback_hour for cases where no sleep is detected within 36h), `manual` (advanced via service call `morning_brief.advance_day`). Strategy is per-instance, configured at instance creation. Returns `(logical_date, cal_offset)` where `cal_offset=0` means logical date matches calendar date, `cal_offset=1` means user hasn't transitioned to today yet.

**D7. Three trigger levels (coexist, configurable per instance).**
L1: schedule (cron-style, time + days-of-week). L2: sensor-based with delay and opt-outs (trigger sensor + delay + opt-out sensors that fire early if changed + fallback hour). L3: external (service-only, user writes their own automation). All three ultimately call the same service `morning_brief.generate.<instance>`. Blueprints provided for L1 and L2 common cases.

**D8. Four AI provider implementations.**
`ha_ai_task` (uses any `ai_task.*` entity available in HA), `anthropic_direct` (direct API with user-supplied key), `openai_direct` (direct API with user-supplied key), `disabled` (degraded mode, brief without AI enrichment). All inherit `AIProvider` ABC. Retry logic: 3 attempts, exponential backoff with base 1 minute, asynchronous (does not block the coordinator).

**D9. AI failure does not break the brief.**
If AI fails after all retries: `ai_status: degraded`, `ai_output` is empty (insights blank, weather_synthesis blank, verdict blank). Brief is still produced, persisted, and notified. The card and renderings handle the degraded case gracefully.

**D10. Hybrid history layer prefers LTS.**
For comparisons requiring historical data: prefer LTS (long-term statistics) over short-term history when both are available. Detect LTS availability per sensor via `state_class` attribute. Detect recorder retention period via the recorder config. Compute the actual coverage for the requested window. On conflict (same date, different value): LTS wins. Index timeseries by date (dict), NEVER by list position.

**D11. Gap handling in history.**
For each comparison: count missing days vs requested window. `0 missing → status: ok`. `0 < missing < 30% → status: partial`, return value with `days_used` field. `≥ 30% missing → status: unreliable`, the card MAY display "—" or hide the comparison. If sensor history doesn't cover the window at all: `status: insufficient_history`.

**D12. Three report types, one instance per type.**
Instance creation chooses one of `morning | evening | weekly`. Each instance is independent (independent config flow, options, fields, categories, AI provider, etc.). To share fields across reports, the "copy fields/categories" mechanism is offered at instance creation (one-shot duplication, not a live link).

**D13. Weekly aggregation per field.**
For weekly reports, each field declares a `weekly_aggregation` enum: `sum | mean | max | min | latest | none`. The UI shows this field only if the field is `visible_in: weekly`. Smart defaults per provider type: cumulative→sum, instantaneous→mean, event_based→mean, state→latest, duration→max.

**D14. Comparisons (V1 closed list).**
8 comparison types: `yesterday` (J-1), `same_weekday_last_week` (J-7), `rolling_avg` (window_days param, range 3-90), `rolling_min` (window_days), `rolling_max` (window_days), `target_value` (target param), `trend` (window_days, linear regression slope), `same_week_last_year` (requires ≥53 weeks of LTS; otherwise returns `insufficient_history`). User selects per field. Defaults: yesterday + same_weekday_last_week + rolling_avg(14) enabled.

**D15. Anomaly detection per field, three modes.**
Per-field config (not global). Modes: `none`, `z_score` (sigmas param, default 2), `static_threshold` (min, max params), `pct_change_vs_rolling_avg` (pct, window_days params). Outputs alerts with severity `info | warning | critical`. User can override severity per field.

**D16. Storage via HA `Store` with FIFO rotation.**
One file per instance: `.storage/morning_brief_<entry_id>`. Default rotation cap: 30 briefs. Configurable in options (range 5-365). Last-write-wins for concurrent writes. Schema versioned (current `version: 1`).

**D17. Single canonical JSON, multiple renderings.**
The `ReportBuilder` produces ONE canonical JSON document (schema in Section 15). All consumers derive their output from this JSON: the sensor entity exposes it in attributes; the markdown fallback renders from it; the notification short renders from it; the Lovelace card consumes it. No alternate "source of truth" exists.

**D18. JSON size handling.**
Sensor entity attributes are limited (~16KB in HA). If the canonical JSON exceeds 16KB: only meta + alerts + a `_truncated: true` flag are exposed in attributes. Full JSON is retrieved via service `morning_brief.get_last_brief`. Card detects `_truncated` and falls back to the service call.

**D19. Notification strategy: option B (manual user setup).**
The integration does NOT auto-install Lovelace views or modify dashboards. It exposes the sensor entity; the user manually adds the card to their dashboard. The repo ships YAML templates in `docs/examples/`. Notifications have a configurable `clickAction` URL pointing wherever the user has placed the card.

**D20. Multilanguage rules.**
Languages supported at launch: FR + EN. Architecture supports adding more languages by adding a JSON file in `translations/` (backend) and `src/i18n/` (frontend). Rules:
- No user-facing string hardcoded anywhere — backend or frontend
- Instance language auto-detected from `hass.config.language` at instance creation
- Override possible per instance
- Fallback EN
- A single label per user-defined field/category (in the instance language). Changing instance language does NOT translate user labels; user re-edits if desired
- Prompt template stays in English; the model is told `{{language}}` and replies in that language

**D21. Drag & drop: deferred to V2.**
HA does not currently support native drag&drop on subentry lists. V1 implements a dedicated "Reorder" step in the options flow with ↑↓ buttons per item. When HA exposes native D&D, migrate.

**D22. AI credentials in `config_entry.data`.**
Credentials (API keys) stored in `config_entry.data` (not `options`). Documented warning in README that these are stored unencrypted on disk per HA convention. Users can also use `secrets.yaml` references.

**D23. Event detection rules (CRITICAL).**
For `event_based` and `duration` providers, "an event occurred" means: a state change happened where the new value is numerically different (epsilon configurable, default 0) from the previous valid value, AND the new value is not `unavailable` or `unknown`. Use `recorder.get_state_changes` not `last_updated`. Deduplicate consecutive identical numeric values. Apply optional `min_debounce` (default 5 minutes) to ignore rapid bouncing.

**D24. Same-week-last-year comparison.**
Requires ≥53 weeks of LTS. If insufficient, return comparison with `status: insufficient_history` and `available_weeks: N`. Compares ISO week N current year vs ISO week N previous year. Aggregation matches the field's `weekly_aggregation` if running in a weekly report; otherwise uses `mean`.

**D25. File size limit.**
No source file exceeds 300 lines without a `# rationale:` comment at the top justifying the exception. Aim for 100-200 lines as the typical size.

---

## 5. Coding rules (NON-NEGOTIABLE)

**R1. No hardcoded user-facing strings.**
All user-facing strings — error messages, labels, descriptions, UI text, log messages users may see — go through translation files. The ONLY exceptions: log messages strictly for developers (DEBUG/INFO level for diagnostic only), internal exception type names, and keys themselves.

**R2. File size cap.**
No file exceeds 300 lines without a `# rationale: <reason>` comment at the top of the file. If you find yourself approaching 250 lines, refactor first.

**R3. Type hints everywhere.**
Backend: Python 3.12+ syntax (`list[int]`, `dict[str, Any]`, `X | None`). No `Any` without justification. Run `mypy --strict` clean.
Frontend: strict TypeScript. No `any`. Run `tsc --strict` clean.

**R4. Docstrings.**
Every module has a one-line docstring at the top. Every public class has a docstring. Every public function/method has a docstring (description + Args + Returns + Raises if applicable).

**R5. ABC inheritance.**
Every provider, AI provider, logical-day strategy, report builder MUST inherit its ABC and pass `validate_config` successfully before instantiation. The factory rejects invalid configs.

**R6. No bare `except`.**
Always catch the specific exception class. `except Exception` is allowed only at the top of an entry point (coordinator update loop, service call entry) to prevent total integration crash; the exception must be logged and the system put into a sane fallback state.

**R7. Index timeseries by date.**
Any data structure representing a time-indexed series MUST be a dict `{date: value}`, never a list where position implies date. The recorder API returns lists; immediately convert.

**R8. Defensive against missing/invalid data.**
Code that reads sensor states MUST handle: entity doesn't exist, state is `unavailable`, state is `unknown`, state is `None`, attribute is missing, attribute is wrong type. None of these propagate as crashes. Each handles with a sensible fallback (e.g., `value.stale=true`) and a log line.

**R9. Async I/O only.**
No blocking I/O in the event loop. File I/O via `hass.async_add_executor_job` or `aiofiles`. HTTP via `aiohttp_client.async_get_clientsession`.

**R10. No long-running operations in setup.**
`async_setup_entry` returns quickly. Long operations (initial data fetch) go in the coordinator's first refresh, which runs after setup.

**R11. Test coverage minimums.**
≥ 70% line coverage on: `providers/`, `history/`, `compute/`, `logical_day/`, `reports/canonical.py`. Each provider has at least: happy path, missing entity, unavailable state, edge case specific to provider (e.g., reset transition for cumulative). Each comparison type has at least: full data, partial, insufficient history.

**R12. No global mutable state.**
All state lives on the coordinator instance or in HA storage. No module-level dicts that hold runtime data.

**R13. Translation files validity.**
Every key added to one translation file MUST be added to all others (FR + EN at minimum). Use a key naming scheme that's stable (`field.config.label` not `lbl1`). The HA test fixture validates this at CI time.

**R14. Conventional commits.**
All commits follow conventional commit format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `build:`, `ci:`. Body explains the why. Reference issues if applicable.

**R15. Lint clean.**
Backend: `ruff check` clean. Frontend: ESLint clean. CI fails on lint errors.

---

## 6. Gotchas (READ BEFORE TOUCHING the relevant subsystem)

**G1. Event detection — DO NOT use `last_updated`.**
`last_updated` changes on every state poll, even when value is identical (heartbeats). Use `recorder.get_state_changes` over a recent window, filter out `unavailable`/`unknown` transitions, deduplicate consecutive identical numeric values (within epsilon). Applies to: `event_based`, `duration` providers.

**G2. LTS partial coverage is common.**
A sensor may have partial LTS because: it was created recently, its `state_class` was added recently, the recorder was paused or had a DB issue, the user manually purged stats. Always check actual coverage of the requested window; never assume.

**G3. `recorder.get_statistics` does not return missing buckets.**
If a day has no data, the returned list simply skips it — there's no `None` placeholder. INDEX BY DATE. Iterate over expected dates, look up in a dict.

**G4. Subentry type declaration.**
`subentry_type` strings are declared via the integration manifest or class decorator. Instance creation is fully dynamic — the user creates as many subentries of each type as they want via the HA UI.

**G5. Availability gate ≠ provider type.**
The gate is a separate concept attached to ANY provider. Implementing the gate logic inside individual providers is wrong — there's a single `availability.py` module that handles gate evaluation and applies the fallback uniformly.

**G6. Logical day `cal_offset` matters.**
After computing `(logical_date, cal_offset)`, downstream code uses BOTH. `cal_offset == 1` means: today's calendar day hasn't "started" from the user's perspective yet. The previous calendar day is the active logical day. Don't drop `cal_offset`.

**G7. Recorder retention vs LTS retention.**
Default recorder retention (short-term history) is 10 days. LTS is kept indefinitely (if state_class present). Users may have customized retention. Detect the actual retention via the recorder config; do not hardcode 10.

**G8. `Store` write is async.**
`store.async_save(data)` is async. Awaiting inside a tight loop is wrong; batch writes.

**G9. Translation file format is HA-specific.**
Use HA's translation conventions (`config`, `options`, `services`, `entity`, `selector`, `exceptions` top-level keys). Validate against the HA developer docs at scaffold time. Test fixture should validate.

**G10. Card never makes HTTP calls.**
The card consumes data from `hass.states[entity_id]` only. For the >16KB fallback, the card calls the integration service via `hass.callService`. No direct HTTP. No fetch.

**G11. `hass.language` may be null.**
On initial load or in some environments, `hass.language` can be undefined. Always default to `en` if null.

**G12. Lit reactive properties.**
LitElement re-renders when reactive properties change. If you mutate an object property without reassigning the property, Lit won't re-render. Always reassign: `this._data = {...this._data, key: newValue}`.

**G13. JSON >16KB → service fallback.**
The sensor entity has limited attribute size. If the canonical JSON exceeds the cap, only meta + alerts go in attributes, with `_truncated: true`. The card detects this and calls `morning_brief.get_last_brief` service for the full JSON. Implement this from the start, don't retrofit.

**G14. AI provider retry must be asynchronous.**
The retry mechanism uses `asyncio.sleep` between attempts. Total time can be several minutes (1min + 2min + 4min backoff). The coordinator should NOT block during this. Either: dispatch the AI call as a task and update the coordinator state when done, OR have the coordinator's update method tolerate long durations (acceptable because triggers are infrequent).

**G15. Weekly week boundaries.**
ISO week starts Monday. User-configurable `start_day_of_week` (0=Mon, 6=Sun). When computing "current week" vs "previous week", use the configured start day, not the calendar default.

---

## 7. Logical day strategies — detailed spec

The logical day is the date the brief is "about" from the user's subjective perspective. It may differ from the calendar date when:
- The user hasn't woken up yet (brief generated at 03:00 — the brief is about yesterday's data, the user is still subjectively "in yesterday")
- The user works night shifts and "their day" starts at noon

Three strategies are implemented in V1. Each returns `(logical_date: date, cal_offset: int)`.

### 7.1 Strategy: `fixed_cutoff` (DEFAULT)

**Config**:
- `cutoff_hour: int` (0-23, default `4`)

**Logic**:
```
now = datetime.now()
if now.hour >= cutoff_hour:
    logical_date = now.date()
    cal_offset = 0
else:
    logical_date = now.date() - timedelta(days=1)
    cal_offset = 1
```

**Use cases**: simplest case, works for 90% of users. Recommended default.

**Edge cases**:
- Time zone changes (DST): handled by using `now` from HA's timezone-aware utility, not naive datetime.
- Cutoff at 0: equivalent to no offset (logical_date == calendar_date always). Document this.

### 7.2 Strategy: `sleep_sensor`

**Config**:
- `sleep_sensor_entity: str` (a `binary_sensor.*` entity)
- `awake_state: str` (the state value indicating awake, e.g., `off` or `false`)
- `hard_fallback_hour: int` (0-23, default `12`) — used if no sleep transition is detected within the lookback window
- `lookback_hours: int` (default `36`)

**Logic**:
1. Query the sensor's state changes over the last `lookback_hours`.
2. Find the most recent transition to `awake_state`.
3. If found:
   - The brief is about the day during which the user was asleep just before that transition.
   - `logical_date = transition_date.date()` if `transition_time >= midnight` of `transition_date`, else `transition_date.date() - timedelta(days=1)`. Concretely: the night that ended at that transition belongs to the calendar day that started before midnight.
   - More simply: `logical_date = (transition_datetime - timedelta(hours=4)).date()` (a "night" started before the wake-up transition belongs to the calendar day that contains the start of that night).
   - `cal_offset = (now.date() - logical_date).days`
4. If no transition found within `lookback_hours`:
   - Apply `hard_fallback_hour` logic identical to `fixed_cutoff` with `cutoff_hour = hard_fallback_hour`.

**Use cases**: users who want the brief based on actual sleep events, not arbitrary cutoff.

**Edge cases**:
- User naps during the day: a nap triggers a `off → on → off` cycle but the brief should not bounce. Mitigation: only consider transitions where the prior sleep duration was at least `min_sleep_duration_minutes` (configurable, default 120). This is a sub-parameter.
- Sensor unavailable: fall back to `hard_fallback_hour` logic, log a warning.
- Multiple transitions in window: use the most recent one.
- User on jet lag soft (sleep schedule shifted by a few hours): the strategy handles this naturally since it follows actual sleep.
- User pulled an all-nighter (no sleep transition in 36h): hard fallback engages.

### 7.3 Strategy: `manual`

**Config**:
- (no parameters)

**Logic**:
- The logical date is stored as state and advanced only by the service `morning_brief.advance_day`.
- On instance creation, initial `logical_date = today, cal_offset = 0`.
- When `advance_day` is called: `logical_date = max(logical_date, today)`, `cal_offset = 0`.

**Use cases**: power users with custom external automations.

### 7.4 Module structure

```
custom_components/morning_brief/logical_day/
├── __init__.py          # registry: STRATEGIES = {"fixed_cutoff": ..., ...}
├── base.py              # ABC LogicalDayStrategy
├── fixed_cutoff.py      # FixedCutoffStrategy
├── sleep_sensor.py      # SleepSensorStrategy
└── manual.py            # ManualStrategy
```

ABC (in `base.py`):

```python
from abc import ABC, abstractmethod
from datetime import date, datetime
import voluptuous as vol

class LogicalDayStrategy(ABC):
    strategy_type: str  # class attribute

    def __init__(self, hass, config: dict):
        self.hass = hass
        self.config = config

    @abstractmethod
    async def get_logical_date(self, now: datetime) -> tuple[date, int]:
        """Returns (logical_date, cal_offset)."""

    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> vol.Schema:
        """Voluptuous schema for the strategy-specific config."""

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Returns list of human-readable errors. Empty if valid."""
```

---

## 8. Field providers — detailed spec for each of 8

All providers inherit `FieldProvider` ABC defined in `providers/base.py`. The ABC defines:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
import voluptuous as vol

@dataclass
class FieldValue:
    raw: float | int | str | None
    unit: str | None
    stale: bool = False
    stale_reason: str | None = None
    as_of: datetime | None = None
    extra: dict = field(default_factory=dict)

class FieldProvider(ABC):
    provider_type: str

    def __init__(self, hass, config: dict):
        self.hass = hass
        self.config = config

    @abstractmethod
    async def get_current_value(self, logical_date: date) -> FieldValue: ...

    @abstractmethod
    async def get_value_for_date(self, target_date: date) -> FieldValue: ...

    @abstractmethod
    async def get_history(self, start_date: date, end_date: date) -> dict[date, FieldValue]: ...

    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> vol.Schema: ...

    @classmethod
    def detect_from_entity(cls, hass, entity_id: str) -> float:
        """Confidence 0.0-1.0 that this provider fits the given entity. Default 0."""
        return 0.0

    @abstractmethod
    def validate_config(self) -> list[str]: ...
```

The **availability gate** is applied externally in `compute/availability.py`, AFTER the provider returns its value. The provider itself is unaware of the gate.

### 8.1 Provider: `cumulative`

**Description**: a sensor whose value increases throughout a period and resets at a known time. The "value of the day" is the increase between two consecutive resets.

**Config**:
- `entity_id: str`
- `reset_hour: int` (0-23, default `0`)

**Use cases**: daily step count, daily energy consumption (kWh), daily sleep total, daily water consumption.

**Behavior**:
- `get_current_value(logical_date)`: fetch the last known value of the sensor between the last reset before/at `logical_date` and the next reset. If logical_date is today and current time < next reset: return the live value (may not be final). If logical_date is past: return the value at `reset_hour` of the day after logical_date (the "final" value for that day).
- `get_value_for_date(target_date)`: same logic for a specific past date.
- `get_history`: iterate over date range, call `get_value_for_date` per day.

**Edge cases**:
- Sensor with `state_class=total_increasing` resets to 0 at the configured hour: standard behavior.
- Sensor that doesn't actually reset (e.g., misconfigured `total_increasing`): document that the user must verify reset behavior. Provider logs a warning if it detects a value larger than yesterday's value at the reset hour.
- Reset hour ≠ 0 (e.g., 11:00 for some watches): user configures `reset_hour=11`.
- Cross-DST transition: convert to UTC for date math.
- Missing day in LTS: returns `FieldValue(raw=None, stale=True, stale_reason="no_data_for_date")`.

**`detect_from_entity` heuristic**:
- `state_class == "total_increasing"` → 0.9
- `state_class == "total"` + `device_class in {energy, water, gas}` → 0.7
- otherwise → 0.0

**Tests required**:
- Happy path: 7 days of consecutive data, fetch each.
- Reset transition: data crosses reset_hour boundary correctly.
- Missing day: returns stale.
- Sensor that didn't reset: detect anomaly and log.

### 8.2 Provider: `instantaneous`

**Description**: a sensor whose value is meaningful at any moment. The "value of the day" is the mean (or last value) over a representative window.

**Config**:
- `entity_id: str`
- `aggregation: str` enum `mean | last` (default `mean`)
- `window_hours_today: int` (default `24`) — for `mean`, the window over which to average for the "today" value

**Use cases**: resting heart rate, body weight (if measured continuously), outdoor temperature, mean 24h HR.

**Behavior**:
- `get_current_value`: for today, average the LTS daily bucket(s) for `logical_date`. For `last`, use the current state value.
- `get_value_for_date`: LTS daily mean for that date.
- `get_history`: range of daily means.

**Edge cases**:
- Sensor without LTS (no `state_class`): `get_current_value` falls back to `state` value; `get_value_for_date` for past returns `insufficient_history`.
- Value is `unavailable`: stale.

**`detect_from_entity` heuristic**:
- `state_class == "measurement"` → 0.8
- numeric state, no state_class → 0.4

**Tests**: happy mean over 24h, last value, missing data, unit conversion handled externally.

### 8.3 Provider: `event_based`

**Description**: a sensor whose value only changes when an event occurs (e.g., stepping on a scale). The "value of the day" is the last value as of the end of the logical day; "today" specifically may be flagged as `not yet measured today` if no event has occurred during the logical day.

**Config**:
- `entity_id: str`
- `epsilon: float` (default `0`) — minimum delta to consider an event "real" (filters numerical noise)
- `min_debounce_minutes: int` (default `5`) — minimum time between two events (filters rapid bouncing)

**Use cases**: body weight from a Wi-Fi scale, manual readings.

**Behavior**:
- `get_current_value(logical_date)`:
  - Fetch state changes via `recorder.get_state_changes` over a sufficient lookback (e.g., 30 days).
  - Filter: remove `unavailable`, `unknown`. Deduplicate consecutive identical values (within epsilon). Apply debounce.
  - Find the most recent valid event.
  - If event timestamp falls within the logical day: `value.raw = event.value, value.stale = False`.
  - Else: `value.raw = event.value, value.stale = True, value.stale_reason = "no_event_today"`.
- `get_value_for_date(target_date)`: find the most recent valid event with timestamp ≤ end of target_date.
- `get_history`: for each date in range, return last event ≤ end of that date.

**Edge cases**:
- No events in lookback: `value.raw = None, value.stale = True, value.stale_reason = "no_data"`.
- Event with identical value (e.g., user weighs the same): kept only if epsilon=0, filtered if epsilon>0.
- Sensor stuck on unavailable: filter rejects, fall back further.

**`detect_from_entity` heuristic**:
- `state_class is None` AND `device_class in {weight, mass}` → 0.7
- `device_class == "weight"` + numeric values + sparse history (many `unavailable` periods) → 0.8
- otherwise → 0.0

**Tests**: happy path with sparse data, unavailable filtering, dedup with epsilon, debounce filter, stale_reason logic.

### 8.4 Provider: `state`

**Description**: a sensor (or binary_sensor) whose value is a state name or enum. Not numeric.

**Config**:
- `entity_id: str`
- `state_mapping: dict[str, dict]` optional — maps raw states to display labels and icons. Example: `{"Rouge": {"label": "Red", "icon": "🔴"}, "Bleu": {"label": "Blue", "icon": "🔵"}}`

**Use cases**: electricity tariff color (Tempo), HA workday sensor, presence state.

**Behavior**:
- `get_current_value`: return current state. Apply mapping if defined.
- `get_value_for_date`: return state as of end-of-day for target_date (last known state).
- `get_history`: same per day.

**Comparisons**: only `yesterday`, `same_weekday_last_week`, `same_week_last_year` make sense (the rest return `not_applicable`).

**Edge cases**: state is `unavailable`: stale. Mapping doesn't cover the state: display raw, log warning.

**`detect_from_entity` heuristic**:
- entity is `binary_sensor.*` → 0.5
- state is non-numeric → 0.6

**Tests**: mapping applied, missing mapping, binary_sensor, unavailable.

### 8.5 Provider: `duration`

**Description**: time elapsed since a reference event. Output is in seconds; display formatted as days/hours/minutes.

**Config**:
- `source_type: str` enum `input_datetime | sensor_last_changed | sensor_attribute_datetime`
- `entity_id: str`
- `attribute_name: str` (only if `source_type == sensor_attribute_datetime`)
- `display_unit: str` enum `auto | days | hours | minutes` (default `auto`)
- `min_debounce_minutes: int` (default `5`) — only for `sensor_last_changed`, to filter heartbeats
- `event_detection: dict` (only for `sensor_last_changed`): same rules as event_based (epsilon, dedup)

**Use cases**: days since last litter maintenance (from input_datetime), time since last visitor (from sensor with last_changed), etc.

**Behavior**:
- `get_current_value(logical_date)`:
  - Resolve the reference timestamp based on `source_type`.
  - Compute `elapsed = end_of_logical_day - reference_timestamp` (in seconds).
  - Format according to `display_unit`.
- `get_value_for_date`: same but with end_of_target_date.
- `get_history`: same per day.

**Comparisons**: `yesterday`, `same_weekday_last_week`, `rolling_max`, `target_value` make sense.

**Edge cases**:
- Reference timestamp in the future: clamp to 0, log warning.
- Reference timestamp unknown: stale.

**Tests**: each source_type, debounce filter, formatting.

### 8.6 Provider: `calendar`

**Description**: read upcoming events from a `calendar.*` entity.

**Config**:
- `calendar_entity_id: str`
- `summary_regex: str | None` — optional regex to filter event summaries
- `window_days: int` (default `7`) — lookahead window
- `max_events: int` (default `1`)

**Use cases**: next vacuum-robot run, next dentist appointment, next work meeting.

**Behavior**:
- `get_current_value(logical_date)`: call `calendar.get_events` for the window `[now, now + window_days]`. Filter by regex. Return first `max_events` matching, structured as `{events: [{summary, start, end, description, location}, ...]}` in `extra`.
- `get_value_for_date`: not particularly meaningful for past dates; return empty.
- `get_history`: returns empty for past dates.

**Comparisons**: not applicable; this provider is informational, no comparisons.

**Tests**: regex filtering, empty calendar, no upcoming events.

### 8.7 Provider: `weather`

**Description**: composite reader of weather data from a `weather.*` entity or a sensor with structured attributes (`current`, `hourly`, `daily`).

**Config**:
- `source_entity_id: str` (a `weather.*` entity or sensor with attributes)
- `source_format: str` enum `ha_weather | structured_attributes` (default auto-detected)
- `hourly_attribute_path: str` (only if `structured_attributes`) — JSON path to the hourly array, e.g., `hourly`
- `daily_attribute_path: str` (similarly)
- `current_attribute_path: str` (similarly)
- `wmo_code_attribute: str` (default `weather_code`)
- `temp_attribute: str` (default `temperature_2m`)
- `precip_proba_attribute: str` (default `precipitation_probability`)
- `precip_sum_attribute: str` (default `precipitation_sum`)
- `temp_min_attribute: str` (default `temperature_2m_min`)
- `temp_max_attribute: str` (default `temperature_2m_max`)

**Use cases**: morning weather brief with current conditions + remaining day hourly + tomorrow forecast.

**Behavior**:
- `get_current_value(logical_date)` outputs a structured `extra` containing:
  ```
  {
    "current": {time, temperature, apparent_temperature, weather_code, weather_text, humidity, wind_speed, wind_direction, precipitation, is_day, cloud_cover},
    "hourly_remaining": [list of hours from `now` to end of calendar day with temp, weather_code, weather_text, precip_proba],
    "today": {weather_code, weather_text, temp_min, temp_max, precip_sum, precip_proba_max},
    "tomorrow": {... same ...},
    "day_after": {... same ...}
  }
  ```
- WMO codes mapped to `weather_text` via a translation table. Mapping in `providers/weather.py` as a constant. Translated to instance language via translations.
- `get_value_for_date(target_date)`: returns the `daily` entry for that date if available in the source.
- `get_history`: returns daily entries for the range.

**Comparisons**: not standard comparisons; the Weather field's `value` is the high-level summary text, and `extra` is the full structured data. Card renders the structured data.

**Edge cases**:
- Source entity unavailable: stale, partial data shown.
- Missing attribute path: log error at config time (validate_config catches it), runtime returns stale.
- WMO code outside known mapping: display raw code, log warning.

**Tests**: ha_weather format, structured_attributes format with custom paths, WMO mapping, missing data.

### 8.8 Provider: `manual`

**Description**: read an `input_number`, `input_text`, or `input_datetime` value.

**Config**:
- `entity_id: str` (an `input_*.*` entity)
- `value_type: str` enum `number | text | datetime` (default auto-detected)

**Use cases**: user-tracked metrics that aren't sensor-driven (mood rating, daily intent, custom counters).

**Behavior**:
- `get_current_value`: read state. Format according to `value_type`.
- `get_value_for_date`: read state as of end of target_date.
- `get_history`: per-day state.

**Comparisons**: only `yesterday`, `same_weekday_last_week`, `target_value` for number type. Others return `not_applicable`.

**Tests**: each value_type, unavailable.

### 8.9 Provider registry and factory

`providers/__init__.py`:

```python
from .base import FieldProvider
from .cumulative import CumulativeProvider
from .instantaneous import InstantaneousProvider
# ... etc

PROVIDERS: dict[str, type[FieldProvider]] = {
    "cumulative": CumulativeProvider,
    "instantaneous": InstantaneousProvider,
    "event_based": EventBasedProvider,
    "state": StateProvider,
    "duration": DurationProvider,
    "calendar": CalendarProvider,
    "weather": WeatherProvider,
    "manual": ManualProvider,
}

def create_provider(hass, provider_type: str, config: dict) -> FieldProvider:
    if provider_type not in PROVIDERS:
        raise ValueError(f"Unknown provider_type: {provider_type}")
    cls = PROVIDERS[provider_type]
    instance = cls(hass, config)
    errors = instance.validate_config()
    if errors:
        raise ValueError(f"Invalid config: {errors}")
    return instance

def detect_provider(hass, entity_id: str) -> tuple[str, float]:
    """Returns the most likely provider type for the entity and its confidence."""
    best = ("instantaneous", 0.0)
    for ptype, cls in PROVIDERS.items():
        score = cls.detect_from_entity(hass, entity_id)
        if score > best[1]:
            best = (ptype, score)
    return best
```

---

## 9. Availability gate

The availability gate is a transverse mechanism applied AFTER a provider returns its value. It allows users to express "this value is only meaningful when condition X holds".

### 9.1 Schema

```python
@dataclass
class AvailabilityGate:
    entity_id: str
    expected_state: str  # the state value that means "available"
```

Stored in field subentry config as `availability_gate: {entity_id, expected_state} | None`.

### 9.2 Logic

In `compute/availability.py`:

```python
async def apply_gate(
    hass,
    field_value: FieldValue,
    gate: AvailabilityGate | None,
    logical_date: date,
    provider: FieldProvider,
) -> FieldValue:
    if gate is None:
        return field_value

    current_gate_state = hass.states.get(gate.entity_id)
    if current_gate_state is None or current_gate_state.state in ("unavailable", "unknown"):
        # Gate sensor itself is unavailable; conservatively, treat as not satisfied
        previous = await provider.get_value_for_date(logical_date - timedelta(days=1))
        return FieldValue(
            raw=previous.raw,
            unit=previous.unit,
            stale=True,
            stale_reason="gate_sensor_unavailable",
            as_of=previous.as_of,
            extra=previous.extra,
        )

    if current_gate_state.state != gate.expected_state:
        # Gate not satisfied: use previous valid day's value
        previous = await provider.get_value_for_date(logical_date - timedelta(days=1))
        return FieldValue(
            raw=previous.raw,
            unit=previous.unit,
            stale=True,
            stale_reason="awaiting_availability",
            as_of=previous.as_of,
            extra=previous.extra,
        )

    # Gate satisfied; return original value
    return field_value
```

### 9.3 Use cases

- `sleep_total`: gate = `{entity_id: binary_sensor.is_sleeping, expected_state: "off"}`. Before wake-up, the sensor is still mid-cycle; we want yesterday's value.
- Energy consumption only after end-of-cycle billing reset.
- Custom: any user-defined "this metric is only valid when condition X".

### 9.4 Tests

- Gate satisfied: returns current value unchanged.
- Gate not satisfied: returns previous day with `stale=True, stale_reason="awaiting_availability"`.
- Gate sensor unavailable: same fallback with `stale_reason="gate_sensor_unavailable"`.

---

## 10. History hybrid layer

The history layer is the most subtle part of the integration. It abstracts access to historical data, hiding the LTS vs short-term distinction from callers.

### 10.1 Components

```
history/
├── lts.py           # Wraps recorder.get_statistics
├── short_term.py    # Wraps recorder.get_state_changes
├── event_detector.py # Filters heartbeats / unavailable / duplicates
└── hybrid.py        # Orchestrates LTS + short-term with conflict resolution
```

### 10.2 `lts.py` interface

```python
async def get_lts_daily(
    hass,
    entity_id: str,
    start_date: date,
    end_date: date,
    aggregation: str,  # "mean" | "change" | "sum" | "max" | "min"
) -> dict[date, float | None]:
    """
    Returns {date: value | None} for each day in [start_date, end_date].
    Value is None if the day has no LTS bucket (gap).
    Raises HistoryError if the entity has no LTS at all (no state_class).
    """
```

Internally calls `recorder.get_statistics` with `period="day"` and the requested `types`. Indexes results by date (parses ISO date from `start` field).

### 10.3 `short_term.py` interface

```python
async def get_short_term(
    hass,
    entity_id: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> list[StateChange]:
    """
    Returns list of state changes ordered by timestamp.
    Each StateChange: {timestamp, state, attributes}.
    """

async def get_short_term_daily_aggregate(
    hass,
    entity_id: str,
    start_date: date,
    end_date: date,
    aggregation: str,
) -> dict[date, float | None]:
    """
    Fetches raw state changes and aggregates per day.
    Useful for sensors without LTS.
    """
```

### 10.4 `event_detector.py`

Pure functions, no I/O:

```python
def filter_valid_changes(
    changes: list[StateChange],
    epsilon: float = 0.0,
    min_debounce_seconds: int = 300,
) -> list[StateChange]:
    """
    1. Reject states == 'unavailable' or 'unknown'
    2. Deduplicate consecutive identical numeric values (within epsilon)
    3. Apply debounce: if two consecutive valid events are < min_debounce apart, keep only the first
    Returns filtered list, ordered by timestamp.
    """
```

### 10.5 `hybrid.py` orchestration

The main interface used by callers:

```python
@dataclass
class HistoryQuery:
    entity_id: str
    start_date: date
    end_date: date
    aggregation: str  # "mean" | "change" | "sum" | "max" | "min" | "last"

@dataclass
class HistoryResult:
    data: dict[date, float | None]  # indexed by date, None for missing days
    status: str  # "ok" | "partial" | "insufficient_history" | "unreliable"
    days_used: int
    days_expected: int
    sources_used: list[str]  # e.g., ["lts", "short_term"]

async def query(hass, q: HistoryQuery) -> HistoryResult:
    expected_days = (q.end_date - q.start_date).days + 1
    result: dict[date, float | None] = {d: None for d in iter_dates(q.start_date, q.end_date)}
    sources = []

    # Try LTS first
    has_lts = entity_has_lts(hass, q.entity_id)
    if has_lts:
        try:
            lts_data = await get_lts_daily(hass, q.entity_id, q.start_date, q.end_date, q.aggregation)
            for date, value in lts_data.items():
                if value is not None:
                    result[date] = value
            sources.append("lts")
        except HistoryError as e:
            log.warning("LTS query failed: %s", e)

    # Fill gaps with short-term where possible
    short_term_retention_days = get_recorder_retention(hass)
    short_term_start = max(q.start_date, date.today() - timedelta(days=short_term_retention_days))
    if any(result[d] is None for d in result):
        try:
            st_data = await get_short_term_daily_aggregate(hass, q.entity_id, short_term_start, q.end_date, q.aggregation)
            for date, value in st_data.items():
                if result.get(date) is None and value is not None:
                    result[date] = value
            sources.append("short_term")
        except Exception as e:
            log.warning("Short-term query failed: %s", e)

    # Compute status
    missing = sum(1 for v in result.values() if v is None)
    days_used = expected_days - missing
    if days_used == 0:
        status = "insufficient_history"
    elif missing == 0:
        status = "ok"
    elif missing / expected_days > 0.30:
        status = "unreliable"
    else:
        status = "partial"

    return HistoryResult(
        data=result,
        status=status,
        days_used=days_used,
        days_expected=expected_days,
        sources_used=sources,
    )
```

### 10.6 Conflict resolution

When both LTS and short-term return values for the same date: LTS wins (D10). The implementation above naturally does this (we only fill from short-term where LTS is missing).

### 10.7 Tests

Required scenarios:
- LTS-only coverage (full window).
- Short-term-only coverage (no state_class, recent days).
- Mixed: LTS for older dates, short-term for last 5 days (newer than LTS purge horizon — rare but possible if LTS write is delayed).
- Gap in middle: status = "partial".
- Mostly missing: status = "unreliable".
- No data at all: status = "insufficient_history".
- Conflict: LTS=10, short-term=12 for same date → result=10.
- Sensor with state_class added recently: LTS starts mid-window.
- Sensor renamed (changed statistic_id): document as out of V1 scope, return based on current statistic_id.

---

## 11. Comparisons — 8 types V1

All comparisons live in `compute/comparisons.py`. They take a `FieldProvider`, a `logical_date`, and a `ComparisonConfig`, and return a `Comparison` result.

### 11.1 Common output structure

```python
@dataclass
class Comparison:
    type: str
    window_days: int | None
    value: float | None
    formatted: str
    delta: float | None
    delta_formatted: str
    direction: str  # "up" | "down" | "flat"
    interpretation: str  # "improvement" | "worsening" | "neutral"
    status: str  # "ok" | "partial" | "insufficient_history" | "unreliable" | "not_applicable"
    days_used: int | None  # for windowed comparisons
```

`interpretation` is computed from `direction` and the field's `direction_preference`:
- `direction == "up"` + `direction_preference == "higher_is_better"` → improvement
- `direction == "up"` + `direction_preference == "lower_is_better"` → worsening
- `direction == "down"` + opposite → improvement
- `direction == "flat"` or `direction_preference == "neutral"` → neutral

### 11.2 Type: `yesterday`

```python
async def compare_yesterday(provider, current_value, logical_date) -> Comparison:
    prev = await provider.get_value_for_date(logical_date - timedelta(days=1))
    if prev.raw is None or current_value.raw is None:
        return Comparison(type="yesterday", ..., status="insufficient_history")
    delta = current_value.raw - prev.raw
    return Comparison(type="yesterday", value=prev.raw, delta=delta, direction=..., status="ok")
```

### 11.3 Type: `same_weekday_last_week`

Same logic, with `logical_date - timedelta(days=7)`.

### 11.4 Type: `rolling_avg`

```python
async def compare_rolling_avg(provider, current_value, logical_date, window_days) -> Comparison:
    start = logical_date - timedelta(days=window_days)
    end = logical_date - timedelta(days=1)  # exclude logical_date itself from the average
    result = await history.query(HistoryQuery(provider.config["entity_id"], start, end, "mean"))
    valid = [v for v in result.data.values() if v is not None]
    if not valid:
        return Comparison(..., status="insufficient_history")
    avg = sum(valid) / len(valid)
    delta = current_value.raw - avg
    return Comparison(
        type="rolling_avg",
        window_days=window_days,
        value=avg,
        delta=delta,
        direction=...,
        status=result.status,
        days_used=result.days_used,
    )
```

### 11.5 Type: `rolling_min` / `rolling_max`

Similar; aggregation `min` or `max` over the window.

### 11.6 Type: `target_value`

```python
def compare_target(current_value, target) -> Comparison:
    delta = current_value.raw - target
    return Comparison(type="target_value", value=target, delta=delta, direction=..., status="ok")
```

### 11.7 Type: `trend`

```python
async def compare_trend(provider, current_value, logical_date, window_days) -> Comparison:
    start = logical_date - timedelta(days=window_days)
    end = logical_date
    result = await history.query(...)
    points = [(i, v) for i, (d, v) in enumerate(sorted(result.data.items())) if v is not None]
    if len(points) < 3:
        return Comparison(..., status="insufficient_history")
    slope = linear_regression_slope(points)
    return Comparison(
        type="trend",
        window_days=window_days,
        value=slope,  # units per day
        delta=None,
        direction="up" if slope > epsilon else "down" if slope < -epsilon else "flat",
        status=result.status,
        days_used=result.days_used,
    )
```

Use simple least-squares (no scipy dependency).

### 11.8 Type: `same_week_last_year`

```python
async def compare_same_week_last_year(provider, current_value, logical_date, weekly_aggregation="mean") -> Comparison:
    last_year_iso_week_start = compute_iso_week_start_last_year(logical_date)
    last_year_iso_week_end = last_year_iso_week_start + timedelta(days=6)

    if (date.today() - last_year_iso_week_start).days < 365:
        return Comparison(type="same_week_last_year", status="insufficient_history")

    result = await history.query(HistoryQuery(
        entity_id=provider.config["entity_id"],
        start_date=last_year_iso_week_start,
        end_date=last_year_iso_week_end,
        aggregation=weekly_aggregation,
    ))

    valid = [v for v in result.data.values() if v is not None]
    if not valid:
        return Comparison(..., status="insufficient_history")

    if weekly_aggregation == "sum":
        agg = sum(valid)
    elif weekly_aggregation == "mean":
        agg = sum(valid) / len(valid)
    elif weekly_aggregation == "max":
        agg = max(valid)
    elif weekly_aggregation == "min":
        agg = min(valid)
    elif weekly_aggregation == "latest":
        agg = sorted(result.data.items())[-1][1]
    else:
        agg = sum(valid) / len(valid)

    delta = current_value.raw - agg
    return Comparison(
        type="same_week_last_year",
        value=agg,
        delta=delta,
        direction=...,
        status=result.status,
        days_used=result.days_used,
    )
```

### 11.9 Comparisons dispatcher

```python
async def evaluate_comparisons(
    provider, current_value, logical_date, field_config, direction_preference
) -> list[Comparison]:
    results = []
    for comp in field_config["comparisons"]:
        ctype = comp["type"]
        if ctype == "yesterday":
            r = await compare_yesterday(provider, current_value, logical_date)
        elif ctype == "same_weekday_last_week":
            r = await compare_same_weekday_last_week(provider, current_value, logical_date)
        elif ctype == "rolling_avg":
            r = await compare_rolling_avg(provider, current_value, logical_date, comp["window_days"])
        # ... etc
        r.interpretation = compute_interpretation(r.direction, direction_preference)
        r.formatted = format_value(r.value, field_config["unit"])
        r.delta_formatted = format_delta(r.delta, field_config["unit"])
        results.append(r)
    return results
```

### 11.10 Tests

Per comparison type: happy path, insufficient history, partial, unreliable, edge case (e.g., current_value None).

---

## 12. Anomaly detection

Per-field, configurable. Lives in `compute/anomaly.py`.

### 12.1 Modes

- `none`: no anomaly check.
- `z_score`: `|current - rolling_mean| / rolling_std > sigmas`. Config: `sigmas: float` (default 2.0), `window_days: int` (default 14).
- `static_threshold`: `current < min_value OR current > max_value`. Config: `min_value: float | None`, `max_value: float | None`.
- `pct_change_vs_rolling_avg`: `|current - rolling_mean| / rolling_mean * 100 > pct`. Config: `pct: float`, `window_days: int`.

### 12.2 Output

```python
@dataclass
class AnomalyResult:
    detected: bool
    severity: str  # "info" | "warning" | "critical"
    mode: str
    message_key: str  # translation key for the alert message
    raw_value: float
    threshold: float | None
```

Severity defaults: `z_score >= 3σ` → critical, `≥ 2σ` → warning, else `info` (rare). For `static_threshold` and `pct_change`, severity is configurable.

### 12.3 Integration with alerts

When `detected=True`, the canonical JSON's `alerts` array receives an entry with `source: "anomaly"`, `field_id: <field>`, severity, message (resolved via translations).

### 12.4 Tests

Per mode: detected, not detected, edge cases (zero std, missing data).

---

## 13. AI providers

### 13.1 ABC

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AIResult:
    status: str  # "ok" | "error"
    content: str | None  # raw JSON string from model
    error_message: str | None
    tokens_used: int | None
    duration_ms: int | None

class AIProvider(ABC):
    provider_type: str

    def __init__(self, hass, config: dict):
        self.hass = hass
        self.config = config

    @abstractmethod
    async def generate(self, prompt: str, language: str, max_tokens: int = 2000) -> AIResult: ...

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Quick check that credentials work. May make a minimal API call."""
```

### 13.2 `disabled.py`

```python
class DisabledProvider(AIProvider):
    provider_type = "disabled"

    async def generate(self, prompt, language, max_tokens=2000) -> AIResult:
        return AIResult(status="ok", content=json.dumps({
            "alertes_formulees": [],
            "insights": {},
            "weather_synthesis": "",
            "verdict": ""
        }), error_message=None, tokens_used=0, duration_ms=0)

    async def validate_credentials(self) -> bool:
        return True
```

(Returns an empty but valid JSON envelope. The brief is generated without AI commentary.)

### 13.3 `ha_ai_task.py`

```python
class HAAITaskProvider(AIProvider):
    provider_type = "ha_ai_task"

    def __init__(self, hass, config):
        super().__init__(hass, config)
        self.entity_id = config["entity_id"]  # e.g., "ai_task.google_ai_task"

    async def generate(self, prompt, language, max_tokens=2000) -> AIResult:
        start = time.monotonic()
        try:
            response = await self.hass.services.async_call(
                "ai_task", "generate_data",
                {
                    "entity_id": self.entity_id,
                    "task_name": "Morning Brief",
                    "instructions": prompt,
                },
                blocking=True,
                return_response=True,
            )
            duration = int((time.monotonic() - start) * 1000)
            if not response or "data" not in response:
                return AIResult(status="error", content=None, error_message="empty_response", tokens_used=None, duration_ms=duration)
            return AIResult(status="ok", content=response["data"], error_message=None, tokens_used=None, duration_ms=duration)
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return AIResult(status="error", content=None, error_message=str(e), tokens_used=None, duration_ms=duration)

    async def validate_credentials(self) -> bool:
        return self.entity_id in self.hass.states.async_entity_ids("ai_task")
```

### 13.4 `anthropic_direct.py`

```python
class AnthropicDirectProvider(AIProvider):
    provider_type = "anthropic_direct"
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, hass, config):
        super().__init__(hass, config)
        self.api_key = config["api_key"]
        self.model = config.get("model", "claude-sonnet-4-7")

    async def generate(self, prompt, language, max_tokens=2000) -> AIResult:
        session = aiohttp_client.async_get_clientsession(self.hass)
        start = time.monotonic()
        try:
            async with session.post(
                self.API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                duration = int((time.monotonic() - start) * 1000)
                if resp.status != 200:
                    body = await resp.text()
                    return AIResult(status="error", content=None, error_message=f"http_{resp.status}: {body[:200]}", tokens_used=None, duration_ms=duration)
                data = await resp.json()
                content = data["content"][0]["text"]
                tokens = data.get("usage", {}).get("output_tokens")
                return AIResult(status="ok", content=content, error_message=None, tokens_used=tokens, duration_ms=duration)
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return AIResult(status="error", content=None, error_message=str(e), tokens_used=None, duration_ms=duration)

    async def validate_credentials(self) -> bool:
        result = await self.generate("ping", "en", max_tokens=10)
        return result.status == "ok"
```

### 13.5 `openai_direct.py`

Analogous, with OpenAI API endpoint and request format. Config: `api_key`, `model` (default `gpt-4o-mini`).

### 13.6 `retry.py`

```python
async def generate_with_retry(
    provider: AIProvider,
    prompt: str,
    language: str,
    max_attempts: int = 3,
    base_delay_seconds: int = 60,
) -> AIResult:
    last_result = None
    for attempt in range(max_attempts):
        result = await provider.generate(prompt, language)
        if result.status == "ok" and result.content:
            try:
                # Validate JSON
                json.loads(result.content)
                return result
            except json.JSONDecodeError:
                log.warning("AI returned invalid JSON on attempt %d", attempt + 1)
        last_result = result
        if attempt < max_attempts - 1:
            delay = base_delay_seconds * (2 ** attempt)  # 60, 120, 240
            await asyncio.sleep(delay)
    return last_result
```

### 13.7 Prompt templates

Files in `prompts/`:
- `morning_v1.txt`
- `evening_v1.txt`
- `weekly_v1.txt`

All in English. Use Jinja2 templating. Variables injected at runtime:

```jinja2
You are the morning brief assistant. You receive a JSON payload describing the user's metrics.

============================================================
LANGUAGE: {{ language }}
You MUST respond in {{ language }} ({{ "French" if language == "fr" else "English" }}).
============================================================

CONTEXT
The brief is about the logical date: {{ data.meta.logical_date }}.
The calendar date is: {{ data.meta.calendar_date }}.
cal_offset is {{ data.meta.logical_day_offset }} (0 = normal, 1 = user hasn't transitioned to today yet).

[rest of the prompt with field structure, expected response format, rules, etc.]

USER CUSTOM CONTEXT (optional, user-provided):
{{ user_custom_context | default("(none)") }}

PREVIOUS BRIEFS (last 2, for context on persistent trends):
{{ previous_briefs_json | default("(none)") }}

PAYLOAD:
{{ data_json }}

OUTPUT FORMAT (JSON only, no markdown, no fences):
{
  "alertes_formulees": [{ "text": "...", "severity": "critical|warning" }],
  "insights": {
    "<category_id>": "1-2 sentences in {{ language }}, or empty string"
  },
  "weather_synthesis": "3-5 sentences in {{ language }}, or empty string",
  "verdict": "2-3 sentences in {{ language }}"
}
```

The `prompt_template.py` module renders the template with the variables and is editable per-instance via options (advanced section).

### 13.8 Tests

- Each provider with mocked HTTP/service responses
- Retry: success on first try, success on second try after delay, all-fail
- Disabled returns valid JSON
- Invalid JSON response triggers retry

---

## 14. Report builders

Three report types, all inheriting `ReportBuilder` ABC.

### 14.1 ABC

```python
class ReportBuilder(ABC):
    report_type: str  # "morning" | "evening" | "weekly"

    def __init__(self, hass, coordinator):
        self.hass = hass
        self.coordinator = coordinator

    @abstractmethod
    async def build(self, logical_date: date) -> dict:
        """Returns the canonical JSON dict (Section 15)."""
```

### 14.2 `morning.py`

The flagship report.

- Uses `logical_day_strategy` to compute `logical_date` and `cal_offset`.
- For each field configured `visible_in: morning`:
  - Resolves provider via factory
  - Calls `provider.get_current_value(logical_date)`
  - Applies availability gate
  - Computes all configured comparisons
  - Runs anomaly detection
- Aggregates alerts from anomalies + battery low + HA health (optional, separate sub-module)
- Builds the canonical JSON via `canonical.py`
- Calls AI provider with the prompt
- Merges AI output into the JSON

### 14.3 `evening.py`

- `cal_offset` always 0 (the day "ending" is the current calendar day)
- Same field iteration logic, filtered to `visible_in: evening`
- Special category preferences: weather section emphasizes "tomorrow" rather than "today remaining"
- AI prompt template differs (`evening_v1.txt`) — wording oriented to recap-and-anticipate

### 14.4 `weekly.py`

- Logical period is "the week ending on `logical_date - 1`" or "the current week" depending on configuration.
- `week_start_day_of_week: int` (0=Mon, 6=Sun, default 0).
- Weekly window: `start = most_recent_week_start, end = start + 6 days`.
- For each field configured `visible_in: weekly`:
  - Computes the weekly aggregate based on `weekly_aggregation`
  - Sparkline data: 7 daily values for the current week
  - Comparisons: `current_week vs previous_week`, `current_week vs avg_4_weeks`, `same_week_last_year`
- AI prompt template: `weekly_v1.txt`, emphasizing trends.

### 14.5 `canonical.py`

The single function that produces the canonical JSON. Takes the resolved fields, comparisons, AI output, etc., and assembles the dict matching Section 15 schema.

```python
async def build_canonical_json(
    instance_id: str,
    instance_name: str,
    report_type: str,
    language: str,
    logical_date: date,
    cal_offset: int,
    fields_resolved: list[ResolvedField],
    categories: list[CategoryConfig],
    ai_output: dict,
    ha_health: dict,
    previous_briefs_refs: list[str],
    duration_ms: int,
) -> dict:
    ...
```

### 14.6 Tests

End-to-end test per report type with mocked sensors and AI, verifying JSON structure matches schema.

---

## 15. Canonical JSON schema (V1)

This is THE schema. The card and renderings depend on it. Schema version field allows future migrations.

```json
{
  "schema_version": 1,
  "meta": {
    "instance_id": "string (uuid)",
    "instance_name": "string",
    "report_type": "morning|evening|weekly",
    "language": "fr|en",
    "generated_at": "ISO8601 with timezone",
    "calendar_date": "YYYY-MM-DD",
    "logical_date": "YYYY-MM-DD",
    "logical_day_strategy": "fixed_cutoff|sleep_sensor|manual",
    "logical_day_offset": 0,
    "ai_status": "ok|degraded|disabled",
    "ai_provider": "string or null",
    "ai_error": "string or null (only if degraded)",
    "duration_ms": 0,
    "_truncated": false
  },
  "alerts": [
    {
      "severity": "critical|warning|info",
      "source": "anomaly|battery|ha_health|custom",
      "field_id": "string or null",
      "message": "string (translated)",
      "raw_value": "number or null",
      "threshold": "number or null"
    }
  ],
  "categories": [
    {
      "id": "string (slug)",
      "label": "string (instance language)",
      "icon": "string (emoji or mdi:)",
      "order": 0,
      "display_when_empty": false,
      "fields": [
        {
          "id": "string (slug, stable)",
          "label": "string (instance language)",
          "icon": "string",
          "order": 0,
          "provider_type": "cumulative|instantaneous|event_based|state|duration|calendar|weather|manual",
          "value": {
            "raw": "number|string|null",
            "formatted": "string",
            "unit": "string or null",
            "stale": false,
            "stale_reason": "string or null (no_data|no_event_today|awaiting_availability|gate_sensor_unavailable|...)",
            "as_of": "ISO8601 or null"
          },
          "extra": {},
          "comparisons": [
            {
              "type": "yesterday|same_weekday_last_week|rolling_avg|rolling_min|rolling_max|target_value|trend|same_week_last_year",
              "window_days": "int or null",
              "value": "number or null",
              "formatted": "string",
              "delta": "number or null",
              "delta_formatted": "string",
              "direction": "up|down|flat",
              "interpretation": "improvement|worsening|neutral",
              "status": "ok|partial|insufficient_history|unreliable|not_applicable",
              "days_used": "int or null"
            }
          ],
          "anomaly": {
            "detected": false,
            "severity": "info|warning|critical",
            "mode": "string",
            "message": "string (translated)",
            "raw_value": 0,
            "threshold": 0
          },
          "sparkline_data": [],
          "direction_preference": "higher_is_better|lower_is_better|neutral"
        }
      ]
    }
  ],
  "ai_output": {
    "category_insights": { "<category_id>": "string" },
    "weather_synthesis": "string",
    "verdict": "string"
  },
  "ha_health": {
    "status": "ok|warning|critical",
    "alerts": [],
    "data": {
      "cpu_pct": 0,
      "ram_pct": 0,
      "db_size_mib": 0
    }
  },
  "previous_briefs_refs": ["uuid_n_minus_1", "uuid_n_minus_2"]
}
```

**Truncation handling**: if `len(json.dumps(payload)) > 16000`, attributes contain only `meta`, `alerts`, `_truncated: true`, `previous_briefs_refs`. Full payload accessible via `morning_brief.get_last_brief` service.

---

## 16. Triggers — 3 levels

All three levels coexist; user picks one per instance.

### 16.1 Level 1 — `schedule`

**Config**:
- `time: str` (HH:MM)
- `days_of_week: list[int]` (0=Mon, 6=Sun)

**Implementation**: `triggers/schedule.py` registers a `time_pattern` listener via `async_track_time_change`. When fired on a configured day, calls `coordinator.async_refresh()` (which triggers a brief generation).

### 16.2 Level 2 — `sensor_based`

**Config**:
- `trigger_entity_id: str` (the sensor to watch)
- `trigger_to_state: str` (the state value that signals "trigger fires")
- `delay_minutes: int` (wait time after the trigger fires, default 30)
- `optout_entities: list[str]` (sensors whose change during the delay causes immediate execution)
- `fallback_hour: int` (0-23, default 12) — if trigger doesn't fire by this hour, force execution
- `fallback_active: bool` (default true)

**Logic**: `triggers/sensor_based.py` implements a state machine:
1. Listen for `trigger_entity_id` state changes.
2. When transition to `trigger_to_state` detected: start `delay_minutes` countdown.
3. During countdown: listen for any optout_entity state change → cancel countdown, execute immediately.
4. If countdown elapses normally: execute.
5. Separately: at `fallback_hour` on configured days, check if execution already happened today; if not, execute.

Uses `async_track_state_change_event` + `async_call_later`.

**This is the case the user (Ivan) currently uses with his sleep sensor + weight scale opt-out.**

### 16.3 Level 3 — `external`

**Config**:
- (none)

**Implementation**: No internal trigger. The user writes their own automation that calls service `morning_brief.generate.<instance>`. Blueprints can help.

### 16.4 Blueprints

Two HA blueprints shipped in `blueprints/automation/morning_brief/`:

**`trigger_on_wake.yaml`**:
- Inputs: instance_id (selector for the morning_brief config_entry), sleep sensor, delay minutes, opt-out sensors
- Trigger: state change of sleep sensor
- Actions: delay + optout race + service call

**`trigger_on_schedule.yaml`**:
- Inputs: instance_id, time, days
- Trigger: time pattern
- Actions: service call

### 16.5 Tests

- Schedule fires at correct time/days.
- Sensor-based: trigger fires, delay elapses, execution happens.
- Sensor-based: opt-out fires during delay, immediate execution.
- Sensor-based: fallback hour triggers if no main trigger.
- External: only service call works.

---

## 17. Storage and persistence

### 17.1 Mechanism

Use HA `homeassistant.helpers.storage.Store`. One store per instance, keyed by `entry_id`. File path: `.storage/morning_brief_<entry_id>`.

### 17.2 Schema (`version: 1`)

```python
{
    "version": 1,
    "minor_version": 0,
    "data": {
        "briefs": [
            {
                "uuid": "string",
                "generated_at": "ISO8601",
                "report_type": "morning|evening|weekly",
                "logical_date": "YYYY-MM-DD",
                "canonical_json": {...},
                "rendered_markdown": "string",
                "notification_short": "string"
            }
        ]
    }
}
```

### 17.3 Operations

```python
class BriefStore:
    def __init__(self, hass, entry_id, retention: int = 30):
        self._store = Store(hass, version=1, key=f"morning_brief_{entry_id}")
        self._retention = retention

    async def add_brief(self, brief: dict) -> None:
        data = await self._store.async_load() or {"briefs": []}
        data["briefs"].insert(0, brief)  # newest first
        data["briefs"] = data["briefs"][:self._retention]
        await self._store.async_save(data)

    async def list_briefs(self) -> list[dict]:
        data = await self._store.async_load() or {"briefs": []}
        return data["briefs"]

    async def get_brief(self, uuid: str) -> dict | None:
        for b in await self.list_briefs():
            if b["uuid"] == uuid:
                return b
        return None

    async def get_latest(self) -> dict | None:
        briefs = await self.list_briefs()
        return briefs[0] if briefs else None

    async def clear(self) -> None:
        await self._store.async_save({"briefs": []})
```

### 17.4 Tests

- Add brief, retrieve latest.
- FIFO rotation at retention limit.
- Get by uuid.
- Clear.
- Concurrent writes (last-write-wins is acceptable).

---

## 18. Entities, services, events exposed

### 18.1 Entities

Per instance (where `<slug>` is a sluggified instance name):

- **`sensor.morning_brief_<slug>`**:
  - `state`: `ok | degraded | error | stale | no_data`
  - `attributes`: canonical JSON (truncated if >16KB) + `last_generation_iso`, `last_brief_uuid`, `_truncated` flag
- **`sensor.morning_brief_<slug>_status`** (lightweight status):
  - `state`: same enum
  - `attributes`: `last_generation_iso`, `last_brief_uuid`, `ai_status`, `ai_provider`
- **`button.morning_brief_<slug>_generate`**:
  - Pressing triggers `generate` service for this instance
- **`button.morning_brief_<slug>_preview`**:
  - Pressing triggers `preview` (returns JSON to last_action_result)

### 18.2 Services (`services.yaml`)

```yaml
generate:
  name: Generate brief
  description: Generate a brief for an instance.
  fields:
    instance_id:
      name: Instance
      description: The morning_brief config entry to use.
      required: true
      selector:
        config_entry:
          integration: morning_brief
    force:
      name: Force regeneration
      description: Generate even if the same logical_date is already in history.
      required: false
      default: false
      selector:
        boolean:

preview:
  name: Preview brief
  description: Generate a brief WITHOUT persisting or notifying. Returns the JSON in the response.
  fields:
    instance_id: { ... }

advance_day:
  name: Advance logical day
  description: For "manual" logical_day strategy — advances the logical date.
  fields:
    instance_id: { ... }

clear_history:
  name: Clear history
  description: Delete all stored briefs for an instance.
  fields:
    instance_id: { ... }

test_ai_provider:
  name: Test AI provider
  description: Test the configured AI provider's credentials.
  fields:
    instance_id: { ... }

get_last_brief:
  name: Get last brief
  description: Returns the most recent brief's canonical JSON. Used by the card to fetch full JSON when truncated.
  fields:
    instance_id: { ... }

get_brief_by_uuid:
  name: Get brief by UUID
  description: Retrieves a specific past brief.
  fields:
    instance_id: { ... }
    uuid: { required: true, selector: { text: } }

reorder_fields:
  name: Reorder fields
  description: Set the display order for fields (advanced; alternative to GUI reorder view).
  fields:
    instance_id: { ... }
    ordered_field_ids: { required: true, selector: { object: } }
```

All services return responses where applicable. Use `supports_response: only` or `supports_response: optional` per HA conventions.

### 18.3 Events emitted

- `morning_brief_generated`:
  ```json
  {
    "instance_id": "string",
    "instance_name": "string",
    "report_type": "string",
    "logical_date": "YYYY-MM-DD",
    "status": "ok|degraded|error",
    "brief_uuid": "string"
  }
  ```
- `morning_brief_ai_failed`:
  ```json
  {
    "instance_id": "string",
    "attempt_count": 3,
    "error_message": "string"
  }
  ```

Users can listen to these to chain automations.

---

## 19. Config flow initial (instance creation)

6 steps. Linear flow with conditional sub-steps.

### Step 1: Report type
- Selector: `morning | evening | weekly`

### Step 2: Name and language
- `instance_name: str` (text, e.g., "Brief matinal Ivan")
- `language: str` (default auto-detected from `hass.config.language`, override possible)

### Step 3: Logical day strategy (morning only; skipped for evening and weekly)
- `strategy: str` (`fixed_cutoff | sleep_sensor | manual`)
- Conditional sub-fields:
  - `fixed_cutoff`: `cutoff_hour: int` (0-23, default 4)
  - `sleep_sensor`: `sleep_sensor_entity`, `awake_state`, `hard_fallback_hour`, `lookback_hours`, `min_sleep_duration_minutes`
  - `manual`: no params

### Step 4: Trigger
- `trigger_level: str` (`schedule | sensor_based | external`)
- Conditional sub-fields:
  - `schedule`: `time`, `days_of_week` (multi-select)
  - `sensor_based`: `trigger_entity_id`, `trigger_to_state`, `delay_minutes`, `optout_entities` (multi-select), `fallback_hour`, `fallback_active`
  - `external`: nothing

### Step 5: AI provider
- `ai_provider_type: str` (`ha_ai_task | anthropic_direct | openai_direct | disabled`)
- Conditional sub-fields:
  - `ha_ai_task`: `entity_id` (select from existing `ai_task.*` entities)
  - `anthropic_direct`: `api_key`, `model` (default `claude-sonnet-4-7`)
  - `openai_direct`: `api_key`, `model` (default `gpt-4o-mini`)
  - `disabled`: nothing

### Step 6: Copy from existing instance
- `copy_from_instance: str | None` (select from existing morning_brief instances, or "Start empty")
- If a source is chosen: at the end of the flow, AFTER the entry is created, duplicate all subentries from the source (one-shot).

### Final
- On submit: create config entry. Trigger entry setup. If `report_type == morning` AND `copy_from_instance is None`: create 3 default category subentries (Health, Home, Weather) as a starter pack — labels in instance language, default icons (💪, 🏠, 🌤️), default orders 10, 20, 30.

### Translations

All step titles, descriptions, field labels, error messages translated via `translations/<lang>.json` under `config.step.*`.

### Tests

- Happy path through all 6 steps for each report type.
- Conditional sub-fields appear correctly.
- Copy-from-existing duplicates subentries.
- Starter pack created when no copy source.
- Invalid AI credentials → error displayed.

---

## 20. Options flow

Menu-based, opens to a main menu showing sections. Each section is implemented as a mixin file in `options_flow/`.

### 20.1 Main menu sections

- General (rename instance, change language, change AI provider type/credentials)
- Logical day strategy (morning only)
- Trigger
- Notification
- Persistence (retention count)
- Reorder fields
- Reorder categories
- Advanced (custom prompt template, log level, exposure of `preview` service)

### 20.2 Per-section structure

Each `options_flow/<section>.py` exports an `async_step_<section>` method that's wired into the main `OptionsFlowHandler`.

```python
# options_flow/__init__.py
class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["general", "logical_day", "trigger", "notification", "persistence", "reorder_fields", "reorder_categories", "advanced"],
        )

    # Each step delegates to mixin
    from .general import async_step_general
    from .logical_day import async_step_logical_day
    # ... etc
```

### 20.3 Field and category management

Field add/edit/delete is NOT in the options flow. It's handled by the native subentry UI (see Section 21). The options flow only handles "reorder" because reorder is a custom operation across all field subentries.

---

## 21. Subentries

### 21.1 Declaration

In `manifest.json`:

```json
{
  "domain": "morning_brief",
  "name": "Morning Brief",
  "subentry_types": ["field", "category"]
}
```

(Verify the exact manifest key at scaffold time per current HA documentation.)

### 21.2 Type `field`

Flow handler in `subentries/field/flow.py`.

**Add flow** (multi-step):
1. **Source**: `entity_id`, `provider_type` (auto-detected default, editable), then conditional sub-fields per provider type (e.g., `reset_hour` for cumulative, `epsilon` for event_based, etc.).
2. **Display**: `label` (single, in instance language), `icon`, `category_id` (dropdown dynamically populated from existing category subentries), `unit`, `direction_preference`.
3. **Comparisons**: multi-checkbox for each of 8 types + params (window_days, target_value).
4. **Anomaly detection**: mode + mode-specific params + severity.
5. **Visibility & weekly**: checkboxes for `visible_in: [morning, evening, weekly]` + `weekly_aggregation` (conditional on weekly being enabled).
6. **AI insight policy**: `optional | required | forbidden`.
7. **Availability gate** (optional): `entity_id` + `expected_state`.

**Edit flow**: same screens, pre-filled.

**Delete**: native HA UI confirmation.

### 21.3 Type `category`

Flow handler in `subentries/category/flow.py`.

**Add/Edit flow** (single screen):
- `category_id` (slug, auto-generated from label, editable advanced)
- `label` (in instance language)
- `icon` (emoji or `mdi:*`)
- `order` (int, default highest + 10)
- `display_when_empty` (bool, default false)

### 21.4 Dynamic dropdowns

When the user opens the field flow, the `category_id` dropdown is populated by querying existing category subentries on the entry. If zero exist, show a button "Create category first" that opens the category subentry flow.

### 21.5 Tests

- Add field with each provider type.
- Edit field, persist changes.
- Delete field.
- Add category, dropdown updates in field flow.
- Invalid config (e.g., missing entity_id) → error.

---

## 22. Reorder view

Lives in `options_flow/reorder.py`. Two sub-menus: reorder fields, reorder categories.

### 22.1 UX

Display a list of all field (or category) subentries with their current order. Each row has a label and two buttons: `↑` and `↓`. Pressing a button moves the row by one in the corresponding direction and re-renders.

Underneath, a "Save" button persists the new order. Cancel discards.

### 22.2 Implementation

Use HA's `data_entry_flow` form with a list selector and manual ordering buttons. Since true buttons in forms are awkward, an alternative UX:
- Display all items with an `order` numeric field per item
- Save updates each subentry's `order` field

This is the V1 implementation. When HA exposes true reorder UI, migrate.

### 22.3 Service alternative

For users who want programmatic control: service `morning_brief.reorder_fields` accepts an ordered list of `field_id` and sets `order` values incrementally (10, 20, 30, ...).

---

## 23. Multilanguage rules

### 23.1 Backend translations

File structure (HA convention):
- `translations/en.json`
- `translations/fr.json`

Top-level keys:
- `config`: step titles, descriptions, field labels for the config flow
- `options`: same for options flow
- `services`: service names, descriptions, field descriptions
- `entity`: entity name suffixes
- `selector`: enum option labels
- `exceptions`: user-facing exception messages
- `common`: shared strings (e.g., comparison type names: "yesterday", "previous day", etc.)

Example skeleton:
```json
{
  "config": {
    "step": {
      "user": {
        "title": "Morning Brief setup",
        "description": "Choose the type of report to create.",
        "data": {
          "report_type": "Report type",
          "language": "Language"
        }
      }
    }
  },
  "options": {
    "step": { ... }
  },
  "services": {
    "generate": {
      "name": "Generate brief",
      "description": "..."
    }
  },
  "selector": {
    "report_type": {
      "options": {
        "morning": "Morning",
        "evening": "Evening",
        "weekly": "Weekly"
      }
    }
  },
  "common": {
    "comparisons": {
      "yesterday": "yesterday",
      "same_weekday_last_week": "w-1",
      "rolling_avg": "avg{days}d",
      "rolling_min": "min{days}d",
      "rolling_max": "max{days}d",
      "target_value": "target",
      "trend": "trend{days}d",
      "same_week_last_year": "y-1"
    },
    "stale_reasons": {
      "no_data": "no data",
      "no_event_today": "no event today",
      "awaiting_availability": "awaiting availability",
      "gate_sensor_unavailable": "gate sensor unavailable"
    },
    "weather_codes": {
      "0": "Clear sky",
      "1": "Mainly clear",
      "2": "Partly cloudy",
      "3": "Overcast",
      "45": "Fog",
      "48": "Depositing rime fog",
      "51": "Light drizzle",
      "53": "Moderate drizzle",
      "55": "Dense drizzle",
      "61": "Slight rain",
      "63": "Moderate rain",
      "65": "Heavy rain",
      "71": "Slight snow",
      "73": "Moderate snow",
      "75": "Heavy snow",
      "77": "Snow grains",
      "80": "Slight rain showers",
      "81": "Moderate rain showers",
      "82": "Violent rain showers",
      "85": "Slight snow showers",
      "86": "Heavy snow showers",
      "95": "Thunderstorm",
      "96": "Thunderstorm with slight hail",
      "99": "Thunderstorm with heavy hail"
    }
  }
}
```

### 23.2 Frontend translations

File structure:
- `src/i18n/en.json`
- `src/i18n/fr.json`

Top-level keys:
- `card`: labels used in card UI ("Alerts", "Verdict", "Previous brief", etc.)
- `comparisons`: same comparison labels (for inline display)
- `stale_reasons`: stale reason labels
- `errors`: error messages displayed in card
- `editor`: card editor UI labels

### 23.3 Loader (frontend)

`src/i18n/index.ts`:

```typescript
import en from "./en.json";
import fr from "./fr.json";

const dictionaries: Record<string, any> = { en, fr };

export function t(key: string, lang: string, params?: Record<string, any>): string {
  const effectiveLang = dictionaries[lang] ? lang : "en";
  const dict = dictionaries[effectiveLang];
  let value = key.split(".").reduce((d, k) => d?.[k], dict) ?? key;
  if (params) {
    for (const [pk, pv] of Object.entries(params)) {
      value = value.replace(`{${pk}}`, String(pv));
    }
  }
  return value;
}
```

The card receives the brief's language via `meta.language` in the JSON and uses it for all rendering (not `hass.language`, since the brief might be in a different language than the HA UI).

### 23.4 Rules (enforced)

- Every key added to one file must exist in all others (CI check via a script that diffs key sets).
- No hardcoded user-facing strings. Linters or grep-based CI checks search for likely violations (string literals in UI templates, etc.).
- Adding a new language: add one JSON file in each location, register in loader. No code changes.

---

## 24. Lovelace card — backend contract

The card consumes the canonical JSON from `sensor.morning_brief_<slug>` attributes (truncated if >16KB; full JSON via service).

### 24.1 Data source

```typescript
// In card.ts
const entityState = hass.states[config.entity];
const attrs = entityState.attributes;

let fullJson: CanonicalBrief;
if (attrs._truncated) {
  // Call service to get full JSON
  const result = await hass.callService("morning_brief", "get_last_brief", { instance_id: ... }, true, true);
  fullJson = result.response;
} else {
  fullJson = attrs;  // the JSON is in attributes directly
}
```

### 24.2 History navigation

When user clicks `<`:
- Currently displayed brief uuid is known
- Call service `morning_brief.get_brief_by_uuid` with the previous uuid (from `previous_briefs_refs` or by listing).
- For the very first display: latest brief.

### 24.3 Refresh

Refresh button:
- Calls service `morning_brief.generate` with `force: false`.
- After completion, the sensor entity updates (via state change), and the card re-renders.

---

## 25. Lovelace card — frontend design

### 25.1 LitElement card class

`src/card.ts`:

```typescript
@customElement("morning-brief-card")
export class MorningBriefCard extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @property({ attribute: false }) public config!: MorningBriefCardConfig;

  @state() private _brief: CanonicalBrief | null = null;
  @state() private _historyIndex: number = 0;  // 0 = latest
  @state() private _loading: boolean = false;
  @state() private _error: string | null = null;

  setConfig(config: MorningBriefCardConfig): void { /* validate */ }
  static getStubConfig(): MorningBriefCardConfig { /* defaults */ }
  static getConfigElement(): HTMLElement { /* returns editor */ }

  protected updated(changed: PropertyValues): void {
    if (changed.has("hass") || changed.has("config")) {
      this._loadCurrentBrief();
    }
  }

  render(): TemplateResult { /* described below */ }

  private async _loadCurrentBrief(): Promise<void> { ... }
  private _navigatePrev(): void { ... }
  private _navigateNext(): void { ... }
  private async _refresh(): Promise<void> { ... }
}
```

### 25.2 Card structure (top to bottom)

1. **Header** (`components/header.ts`):
   - `<` `>` buttons (disabled when at boundary)
   - Title (instance_name) + small subtitle with formatted date
   - Action icons: refresh, settings

2. **Alerts section** (`components/alerts.ts`):
   - Shown only if `alerts.length > 0`
   - Background tinted danger/warning depending on max severity
   - List of messages with severity-colored bullets

3. **Categories** (loop over `meta.categories`, one `<category-card>` per category):
   - Each category is a sub-card with its own border, background, header
   - Header: icon + label + (count of fields)
   - Body: list of fields with separators between them
   - Category-specific AI insight (italic, in a tinted box at the end of the category)

4. **Field component** (`components/field.ts`):
   - Layout: left side has `icon + label + small extras + comparisons inline`. Right side has the formatted value (large).
   - For weekly report: a small inline SVG sparkline next to the label.
   - Stale values shown with `stale_reason` label.
   - Comparison deltas colored by `interpretation` (green=improvement, red=worsening, neutral=gray).

5. **Sparkline component** (`components/sparkline.ts`):
   - SVG polyline, 7 points, ~80×20 pixels.
   - Optional last-point marker.
   - Color from CSS theme variable.
   - Visible by default in weekly; opt-in for other report types if user adds sparkline data field (V2 maybe).

6. **Weather section** (`components/weather.ts`):
   - Shown if any field with `provider_type=weather` exists in the brief.
   - Renders the AI's `weather_synthesis` text.
   - May optionally render small icons/temps from the weather field's `extra` data (V2).

7. **Verdict** (`components/verdict.ts`):
   - Shown if `ai_output.verdict` is non-empty.
   - Tinted info background, in exergue.

8. **Footer** (`components/footer.ts`):
   - Small text with metadata: watch battery, HA health summary, logical date.

### 25.3 Compact mode

When `config.compact_mode === true`:
- Comparisons inline hidden (only formatted value shown)
- Alerts condensed: "⚠️ 1 alert — tap to expand" (tapping expands)
- AI category insights hidden
- Sparklines hidden
- Footer hidden
- Verdict kept (essential for actionable info)

### 25.4 CSS

`src/styles/card.css.ts`: a `css` tagged template literal exporting styles. Use HA CSS custom properties:
- `var(--primary-text-color)`
- `var(--secondary-text-color)`
- `var(--card-background-color)`
- `var(--primary-color)` (for accent)
- `var(--error-color)`, `var(--warning-color)`, `var(--success-color)`
- `var(--divider-color)`

Card top-level: `ha-card` element with full HA theming integration.

### 25.5 Tests

- Mock JSON in fixture, render card, check expected DOM.
- Compact mode renders fewer sections.
- Navigation buttons disabled at boundaries.
- Stale fields rendered with stale reason label.
- Refresh triggers service call.

---

## 26. Card editor

`src/editor.ts`: a LitElement form for the card config.

Fields exposed:
- `entity`: entity selector for `sensor.morning_brief_*`
- `compact_mode`: boolean toggle
- `show_categories`: multi-select (loaded dynamically from the entity's last brief categories)
- `hide_fields`: multi-select (loaded dynamically)
- `show_history_nav`: boolean (default true)
- `show_ai_sections`: boolean (default true)
- `show_alerts`: boolean (default true)
- `show_weather`: boolean (default true)
- `show_footer`: boolean (default true)
- `theme_override`: text input for accent color (optional)

All labels via i18n.

---

## 27. Notification rendering

`rendering/notification_short.py` produces the short text for mobile notifications.

### 27.1 Format

3 lines max:

```
Line 1 (only if alerts > 0): 🚨 N alert(s)
Line 2: emoji+value · emoji+value · emoji+value  (3-4 key metrics)
Line 3 (only if verdict non-empty): first sentence of verdict
```

Which 3-4 metrics appear on line 2 is configurable per instance: `notification_pinned_fields: list[str]` (list of field_ids), default = first 3 fields in display order.

### 27.2 Title

Configurable template per instance, default:
- Morning: `Brief matinal — {date} {time}` (in instance language)
- Evening: `Brief du soir — {date} {time}`
- Weekly: `Brief hebdo — {week_start} → {week_end}`

### 27.3 Service call

```python
await hass.services.async_call(
    "notify",
    notification_target_service_name,  # e.g., "mobile_app_pixel_9_pro_xl"
    {
        "title": title,
        "message": notif_short,
        "data": {
            "tag": f"morning_brief_{instance_id}",
            "ttl": 0,
            "priority": "high",
            "clickAction": notification_click_url,
        },
    },
)
```

### 27.4 Optional: persistent_notification

User can also enable `also_create_persistent_notification: bool`. If true, creates an HA persistent notification with the markdown rendering (richer than notification short).

---

## 28. Markdown rendering (fallback)

`rendering/markdown.py` produces a markdown version of the brief for users who don't install the custom card.

### 28.1 Format

```
# Brief {instance_name} — {date} {time}

## 🚨 Alerts
- ...

## 💪 Health
- ⚖️ Weight: **76.59 kg** _(yesterday 76.82 ↓0.23 · w-1 76.86 ↓0.27 · avg14d 76.39 ↑0.20)_
- 😴 Sleep: **7h31** (23:50 → 07:21)
  _(yesterday 5h30 ↑2h01 · w-1 6h39 ↑52min · avg14d 6h31 ↑60min)_
  deep 1h51 (25%)
- ...

_Excellent recovery..._

## 🏠 Home
...

## 🌤️ Weather
Rain expected from 09:00 to 12:00...

> **Verdict**: Good recovery night. Tempo Red — defer washing...

---
🔋 Watch 3.2d · HA OK · Logical date 2026-05-14
```

This markdown is included in `notification_short` data payload (or `data.markdown` field) for clients that support markdown, AND used by the default Lovelace `markdown` card if the user prefers a no-custom-card setup. AND used by `persistent_notification.create` if enabled.

### 28.2 Localization

All labels in the markdown (section headers, "yesterday", "Verdict", etc.) translated via instance language using backend translation files.

---

## 29. Robustness rules

These are the runtime resilience rules that prevent the integration from breaking due to user environment issues.

### 29.1 At setup

- Validate every configured `entity_id` exists in HA. If missing → log warning, mark field as `degraded`, brief generation skips it, generate "repair issue" notification.
- Validate AI provider credentials with a quick `validate_credentials()` call. If failing → log warning, mark instance as `ai_disabled`, brief still generates but with `ai_status: degraded`.
- Validate notification target exists. If missing → log warning, notification is skipped, brief still stored.

### 29.2 At runtime

- Every field resolution wrapped in `try / except Exception`. On exception: log full traceback, mark field as `error`, include in alerts.
- Every comparison wrapped similarly: on exception, comparison status = `unreliable`, message logged.
- AI call wrapped: on persistent failure, `ai_status: degraded`.
- Store write wrapped: on failure, log error, brief notified but not stored.
- Notification call wrapped: on failure, log, brief stored.

### 29.3 No crash propagation

The coordinator's `_async_update_data` method must NEVER raise. It catches all exceptions, packages them into a sensible state, and returns. Worst case: returns the last successful brief unchanged + an alert about the generation failure.

### 29.4 Repair issues

For persistent problems (missing entity, broken AI credentials), use HA's `issue_registry` to surface user-actionable issues in the UI.

---

## 30. Testing requirements

### 30.1 Coverage targets

- `providers/`: ≥ 80%
- `history/`: ≥ 80%
- `compute/`: ≥ 80%
- `logical_day/`: ≥ 80%
- `reports/`: ≥ 70%
- `store.py`: ≥ 90%
- `config_flow.py` + `options_flow/`: ≥ 60%
- `subentries/`: ≥ 60%
- `ai/`: ≥ 70%

### 30.2 Test categories

- Unit tests: per module, fixtures-based.
- Integration tests: full pipeline for one morning brief (mocked sensors + AI).
- Config flow tests: happy paths + validation errors.
- End-to-end: minimal but real — exercise the coordinator, store, sensor entity.

### 30.3 Fixtures

`tests/fixtures/sensor_states.json` — a representative set of HA states for testing.
`tests/fixtures/lts_data.json` — a representative set of LTS query responses.
`tests/conftest.py` — pytest fixtures for HA test setup.

### 30.4 CI

GitHub Actions workflow:
- Lint: `ruff check`
- Type check: `mypy --strict custom_components/morning_brief`
- Tests: `pytest --cov` with coverage report
- HACS validation: `hacs/action`

---

## 31. README requirements

The integration repo's `README.md` is in English and includes the following sections (each with a level-2 header, in this order):

1. **Overview** (1 paragraph)
2. **Features** (bulleted)
3. **Screenshots** (placeholders linking to `docs/img/*.png` to be added later)
4. **Installation** (HACS recommended + manual)
5. **Quick start** (creating a first instance, adding a category, adding a field, generating a brief)
6. **Field providers reference** (one sub-section per provider with config example YAML)
7. **Comparisons reference** (each of 8 types with semantics)
8. **Anomaly detection reference** (3 modes with config examples)
9. **AI providers setup** (per provider, with key acquisition links and config example)
10. **Logical day strategies reference** (3 strategies)
11. **Triggers reference** (3 levels + how to use blueprints)
12. **Notification setup** (configuring notify target + clickAction)
13. **Lovelace card setup** (link to card repo, basic + compact YAML examples)
14. **Service reference** (table of all services)
15. **Events reference** (table)
16. **Multilanguage** (FR/EN supported, how to contribute a new language)
17. **Troubleshooting** (common issues: empty brief, AI errors, missing comparisons, gate not working)
18. **Architecture overview** (1 paragraph + link to `docs/architecture.md`)
19. **Contributing**
20. **License**

The frontend repo's `README.md`:

1. **Overview**
2. **Screenshots**
3. **Installation** (HACS + manual)
4. **Configuration** (full options list with YAML examples)
5. **Compatibility** (which integration version it works with)
6. **Compact mode**
7. **History navigation**
8. **Troubleshooting**
9. **Contributing**
10. **License**

---

## 32. Docs/ contents

- `docs/architecture.md`: deep dive on the architecture (this spec is the source; the docs distill key points for users/contributors).
- `docs/providers.md`: extended provider docs with edge cases and tips.
- `docs/triggers.md`: in-depth triggers + blueprints walkthrough.
- `docs/ai_providers.md`: setup details per AI provider.
- `docs/multilanguage.md`: contribution guide for new languages.
- `docs/examples/lovelace_basic.yaml`: ready-to-paste card config.
- `docs/examples/lovelace_compact.yaml`: compact mode example.
- `docs/examples/automation_level3_external_trigger.yaml`: external trigger example.
- `docs/examples/full_config_export.yaml`: a complete instance config as reference.

---

## 33. Blueprints

### 33.1 `blueprints/automation/morning_brief/trigger_on_wake.yaml`

```yaml
blueprint:
  name: Morning Brief — Trigger on wake
  description: Trigger a Morning Brief generation when a sleep sensor indicates wake-up, with optional opt-out sensors that fire early.
  domain: automation
  input:
    instance_id:
      name: Morning Brief instance
      selector:
        config_entry:
          integration: morning_brief
    sleep_sensor:
      name: Sleep binary_sensor
      selector:
        entity:
          domain: binary_sensor
    awake_state:
      name: Awake state value
      default: "off"
    delay_minutes:
      name: Delay (minutes)
      default: 30
      selector:
        number: { min: 0, max: 120, step: 5, unit_of_measurement: min }
    optout_entities:
      name: Opt-out sensors
      default: []
      selector:
        entity: { multiple: true }
    fallback_hour:
      name: Fallback hour
      default: 12
      selector:
        number: { min: 0, max: 23, unit_of_measurement: h }

# ... trigger + condition + action logic
```

### 33.2 `blueprints/automation/morning_brief/trigger_on_schedule.yaml`

Simpler: time + days + service call.

---

## 34. Lovelace examples YAML

### 34.1 `docs/examples/lovelace_basic.yaml`

```yaml
type: custom:morning-brief-card
entity: sensor.morning_brief_brief_matinal_ivan
```

### 34.2 `docs/examples/lovelace_compact.yaml`

```yaml
type: custom:morning-brief-card
entity: sensor.morning_brief_brief_matinal_ivan
compact_mode: true
show_history_nav: false
show_footer: false
```

### 34.3 Dashboard view example (for users who don't install custom card)

```yaml
title: Morning Brief
path: brief
icon: mdi:weather-sunny
cards:
  - type: markdown
    content: "{{ states.sensor.morning_brief_brief_matinal_ivan.attributes.rendered_markdown }}"
```

---

## 35. HACS configuration

### 35.1 Integration repo `hacs.json`

```json
{
  "name": "Morning Brief",
  "render_readme": true,
  "homeassistant": "X.Y.Z",
  "documentation": "...",
  "country": ["EN"],
  "iot_class": "Local Polling"
}
```

### 35.2 Frontend repo `hacs.json`

```json
{
  "name": "Morning Brief Card",
  "render_readme": true,
  "filename": "morning-brief-card.js"
}
```

---

## 36. Implementation plan (phases)

Implement strictly in this order. Each phase ends with green tests committed. Update `PROGRESS.md` after each unit.

### Phase 1 — Foundation
1. `manifest.json` (verify HA version compat, declare subentry types, list dependencies)
2. `const.py` (DOMAIN, defaults, enums for `report_type`, `provider_type`, `comparison_type`, etc.)
3. `types.py` (TypedDicts, dataclasses: `FieldValue`, `Comparison`, `AnomalyResult`, `AIResult`, `CanonicalBrief`, etc.)
4. `exceptions.py` (custom exceptions)
5. `translations/{en,fr}.json` (skeleton with `config.step.user` filled)
6. `coordinator.py` (DataUpdateCoordinator subclass skeleton)
7. `store.py` (BriefStore with FIFO rotation)
8. `__init__.py` (`async_setup_entry`, `async_unload_entry`, `async_remove_entry`)
9. Tests: `tests/test_store.py` (rotation logic)
10. Commit: `feat: foundation skeleton`

### Phase 2 — History layer
11. `history/lts.py`
12. `history/short_term.py`
13. `history/event_detector.py`
14. `history/hybrid.py`
15. Tests: `tests/history/test_lts.py`, `test_short_term.py`, `test_event_detector.py`, `test_hybrid.py`
16. Commit: `feat: history hybrid layer with LTS and short-term`

### Phase 3 — Providers (one at a time, with tests)
17. `providers/base.py` + `providers/__init__.py` (registry + factory)
18. `providers/instantaneous.py` + tests (simplest)
19. `providers/cumulative.py` + tests
20. `providers/manual.py` + tests
21. `providers/state.py` + tests
22. `providers/event_based.py` + tests
23. `providers/duration.py` + tests
24. `providers/calendar.py` + tests
25. `providers/weather.py` + tests (most complex; verify WMO mapping via translations)
26. Commit per provider: `feat(providers): add <type> provider`

### Phase 4 — Logical day & triggers
27. `logical_day/base.py` + `__init__.py`
28. `logical_day/fixed_cutoff.py` + tests (with DST edge case)
29. `logical_day/sleep_sensor.py` + tests (with nap filter, all-nighter, multiple transitions)
30. `logical_day/manual.py` + tests
31. `triggers/schedule.py`
32. `triggers/sensor_based.py` (with opt-outs and fallback)
33. Tests for triggers (mocked HA scheduler)
34. Commit: `feat: logical day strategies + triggers`

### Phase 5 — Availability gate & comparisons & anomaly
35. `compute/availability.py` + tests
36. `compute/comparisons.py` (all 8 types) + tests per type
37. `compute/anomaly.py` (3 modes) + tests
38. Commit: `feat: comparisons, anomaly, availability gate`

### Phase 6 — AI layer
39. `ai/base.py`
40. `ai/disabled.py` (simplest)
41. `ai/retry.py` + tests
42. `ai/ha_ai_task.py` + tests (mocked service call)
43. `ai/anthropic_direct.py` + tests (mocked HTTP)
44. `ai/openai_direct.py` + tests
45. `ai/prompt_template.py` + tests
46. `prompts/morning_v1.txt`, `evening_v1.txt`, `weekly_v1.txt` (English with Jinja vars)
47. Commit: `feat: AI providers with retry`

### Phase 7 — Reports & canonical JSON
48. `reports/base.py` + `__init__.py`
49. `reports/canonical.py` (builder)
50. `reports/morning.py`
51. `reports/evening.py`
52. `reports/weekly.py` (with weekly_aggregation logic)
53. `rendering/markdown.py`
54. `rendering/notification_short.py`
55. Tests: `tests/reports/test_morning.py` (end-to-end with mocked sensors + mocked AI), then evening, weekly
56. Commit: `feat: report builders + renderings`

### Phase 8 — Config flow & subentries
57. `config_flow.py` (6 steps)
58. `options_flow/general.py`
59. `options_flow/logical_day.py`
60. `options_flow/trigger.py`
61. `options_flow/notification.py`
62. `options_flow/persistence.py`
63. `options_flow/reorder.py` (fields + categories with ↑↓)
64. `options_flow/advanced.py` (prompt template editor)
65. `options_flow/__init__.py` (main menu)
66. `subentries/field/schema.py` (voluptuous schemas per provider type)
67. `subentries/field/flow.py` (multi-step add/edit)
68. `subentries/category/flow.py`
69. Populate `translations/{en,fr}.json` for all flows
70. Tests: config flow happy paths + validation errors
71. Commit: `feat: config flow and subentries`

### Phase 9 — Services, entities, events
72. `services.py` + `services.yaml`
73. `sensor.py` (with truncation handling)
74. `button.py` (generate, preview)
75. Event firing on completion
76. End-to-end test: `tests/test_e2e_morning.py`
77. Commit: `feat: services, entities, events`

### Phase 10 — Frontend card
78. `package.json`, `tsconfig.json`, `rollup.config.js`, ESLint, Prettier
79. `src/types.ts` (mirrors canonical JSON)
80. `src/i18n/en.json`, `fr.json`, `src/i18n/index.ts` (loader)
81. `src/utils/format.ts` (locale-aware numbers/durations)
82. `src/utils/colors.ts`
83. `src/utils/data.ts`
84. `src/utils/history.ts`
85. `src/components/sparkline.ts` (simplest)
86. `src/components/header.ts`
87. `src/components/footer.ts`
88. `src/components/alerts.ts`
89. `src/components/field.ts`
90. `src/components/category.ts`
91. `src/components/weather.ts`
92. `src/components/verdict.ts`
93. `src/styles/card.css.ts`
94. `src/card.ts` (MorningBriefCard, wires components)
95. `src/editor.ts` (config GUI)
96. `src/index.ts` (registration)
97. Bundle config + dist output
98. Tests on key utils + a card smoke test
99. Manual test against a real running integration
100. Commit per significant unit

### Phase 11 — Docs & blueprints & examples
101. `README.md` integration (full TOC from Section 31)
102. `README.md` frontend (TOC from Section 31)
103. `docs/architecture.md`
104. `docs/providers.md`
105. `docs/triggers.md`
106. `docs/ai_providers.md`
107. `docs/multilanguage.md`
108. `docs/examples/*.yaml`
109. `blueprints/automation/morning_brief/trigger_on_wake.yaml`
110. `blueprints/automation/morning_brief/trigger_on_schedule.yaml`
111. `CHANGELOG.md` (both repos)
112. `info.md`, `hacs.json` finalize
113. Commit: `docs: complete documentation`

### Phase 12 — Polish & release prep
114. Run full test suite, fix any failures
115. Run `mypy --strict`, fix any errors
116. Run `ruff check`, fix any errors
117. Frontend: `tsc --strict`, ESLint, run `npm run build` to produce dist
118. Verify HACS validation passes (`hacs/action`)
119. Update `CLAUDE.md`, `PROGRESS.md`, `DECISIONS.md` to reflect final state
120. Tag v1.0.0 in both repos
121. Commit: `chore: release v1.0.0`

---

## 37. Acceptance criteria V1

V1 is "done" when ALL of the following hold:

- [ ] Both repos pass HACS validation (`hacs/action`).
- [ ] All source files ≤ 300 lines (or have `# rationale:` justifying exceptions).
- [ ] Zero hardcoded user-facing strings (manual scan + CI check).
- [ ] Test coverage meets targets from Section 30.1.
- [ ] `mypy --strict` clean on backend.
- [ ] `tsc --strict` + ESLint clean on frontend.
- [ ] Manual end-to-end on a real HA instance succeeds: create instance, add 2 categories, add 5 fields of varying provider types, configure schedule trigger, generate, notification fires, card renders, history navigation works.
- [ ] README complete and accurate in both repos.
- [ ] All `CLAUDE.md`, `PROGRESS.md`, `DECISIONS.md` reflect final state.
- [ ] CHANGELOG.md describes V1 release.
- [ ] Blueprints work when imported into HA.
- [ ] AI degraded mode produces a sensible brief (verified by manually disabling the AI provider).
- [ ] LTS hybrid handles a sensor with state_class added recently (mock test passes).
- [ ] `same_week_last_year` returns `insufficient_history` cleanly for sensors with <53 weeks of LTS.

---

## 38. End-of-session ritual

Before ending ANY session, perform these steps in order. Skipping any step is a violation of the spec.

1. **Update `PROGRESS.md`** — check off completed items, add new items if scope expanded.
2. **Append entry to `Session log`** in each touched `CLAUDE.md` (format: `- YYYY-MM-DD — <summary of work done>`).
3. **Update `Open questions / blockers`** in `CLAUDE.md` — add anything unresolved, remove resolved items.
4. **Append `DECISIONS.md`** if any architectural decision was changed (with explicit user approval).
5. **Run tests** for what you touched: `pytest tests/<touched>` or `npm test`. Commit only when green.
6. **Lint** what you touched.
7. **Commit** with conventional commit format. Body explains the why. Reference issues if applicable.
8. **Push** to a feature branch (do not push directly to main unless explicitly authorized).
9. **Summarize** to the user: what was done, what's pending, what to tackle next session.

---

## 39. Out of scope for V1

These are explicitly NOT in V1. Do not implement them. They are noted here so V2 planning can refer back.

- `Computed` provider (multi-sensor derived). Workaround: user creates a template sensor in HA.
- `REST/External` provider (direct HTTP fetch from a 3rd party API). Workaround: use existing HA integration that exposes a sensor.
- Native drag&drop in subentry lists. We use the Reorder view with ↑↓.
- Custom HTML panel for advanced configuration (a fully custom JS UI). We stick to HA standard config_flow/options_flow.
- Advanced sparklines: multi-series, scrolling, interactive tooltips. V1 sparklines are static 7-point SVG.
- Trigger via webhook (HTTP endpoint exposed by integration). Use the service from a webhook automation if needed.
- Public REST API on the integration. Services suffice.
- Auto-installed Lovelace dashboard. We provide YAML examples; user copy-pastes.
- Auto-mapping of sensors at instance creation (a "wizard" that picks 10 sensors and configures everything). User configures fields one by one.
- Backup/restore of full instance config from a single YAML. User manually re-creates if needed.
- Real-time updates between brief generations. The brief is point-in-time.
- Multiple AI providers per instance (fallback chain). One AI provider per instance.

---

## 40. Concrete real-world cases (sanity check)

These are example field configurations from the user's real setup. They serve as integration tests for the spec. The implementation MUST handle all of these correctly out of the box.

### 40.1 Sleep total

```yaml
field_id: sleep_total
label: "Sommeil"
icon: "😴"
category_id: health
provider_type: cumulative
provider_config:
  entity_id: sensor.amazfit_sleep_total
  reset_hour: 0
availability_gate:
  entity_id: binary_sensor.amazfit_is_sleeping
  expected_state: "off"
unit: min
direction_preference: higher_is_better
comparisons:
  - { type: yesterday }
  - { type: same_weekday_last_week }
  - { type: rolling_avg, window_days: 14 }
anomaly_detection:
  mode: static_threshold
  min_value: 300
  severity_below: warning
visible_in: [morning]
weekly_aggregation: mean
ai_insight_policy: optional
```

**Expected behavior at 8h after wake-up**: gate satisfied (is_sleeping=off), value is yesterday-night-sleep (e.g., 451 min), stale=false. Comparisons rendered.

**Expected behavior at 6h before wake-up**: gate not satisfied (is_sleeping=on), value falls back to previous day's value, stale=true, stale_reason="awaiting_availability". Card shows "Pas encore réveillé".

### 40.2 Body weight (Etekcity scale)

```yaml
field_id: weight
label: "Poids"
icon: "⚖️"
category_id: health
provider_type: event_based
provider_config:
  entity_id: sensor.etekcity_weight
  epsilon: 0.05
  min_debounce_minutes: 5
unit: kg
direction_preference: lower_is_better  # depends on user goal
comparisons:
  - { type: yesterday }
  - { type: same_weekday_last_week }
  - { type: rolling_avg, window_days: 14 }
  - { type: target_value, target: 75 }
anomaly_detection:
  mode: z_score
  sigmas: 3
visible_in: [morning, weekly]
weekly_aggregation: mean
ai_insight_policy: optional
```

**Expected behavior if weighed today**: value=today's weight, stale=false, comparisons computed.

**Expected behavior if NOT weighed today**: value=last recorded weight, stale=true, stale_reason="no_event_today". The "weighed today" status derived from last_changed.

### 40.3 Bender (cat) weight

Same as above but on a different sensor.

### 40.4 Resting heart rate

```yaml
field_id: hr_resting
label: "FC repos"
icon: "💓"
category_id: health
provider_type: instantaneous
provider_config:
  entity_id: sensor.amazfit_hr_resting
  aggregation: last
unit: bpm
direction_preference: lower_is_better
comparisons:
  - { type: yesterday }
  - { type: same_weekday_last_week }
  - { type: rolling_avg, window_days: 14 }
anomaly_detection:
  mode: z_score
  sigmas: 2
visible_in: [morning, weekly]
weekly_aggregation: mean
ai_insight_policy: optional
```

### 40.5 Steps

```yaml
field_id: steps
label: "Pas"
icon: "🏃"
category_id: health
provider_type: cumulative
provider_config:
  entity_id: sensor.amazfit_steps
  reset_hour: 0
unit: ""  # raw integer
direction_preference: higher_is_better
comparisons:
  - { type: yesterday }
  - { type: same_weekday_last_week }
  - { type: rolling_avg, window_days: 14 }
anomaly_detection:
  mode: none
visible_in: [morning, evening, weekly]
weekly_aggregation: sum
ai_insight_policy: optional
```

### 40.6 Litter maintenance duration

```yaml
field_id: litter_days_since_maintenance
label: "Litière"
icon: "🚽"
category_id: cat  # custom category
provider_type: duration
provider_config:
  source_type: input_datetime
  entity_id: input_datetime.litter_last_maintenance
  display_unit: days
unit: days
direction_preference: lower_is_better
comparisons:
  - { type: target_value, target: 6 }
anomaly_detection:
  mode: static_threshold
  max_value: 6
  severity_above: warning
visible_in: [morning, evening]
weekly_aggregation: max
ai_insight_policy: optional
```

### 40.7 Tempo color (state)

```yaml
field_id: tempo_today
label: "Tempo aujourd'hui"
icon: "⚡"
category_id: home
provider_type: state
provider_config:
  entity_id: sensor.rte_tempo_current_color
  state_mapping:
    Bleu: { label: "Bleu", icon: "🔵", color: "#3478e8" }
    Blanc: { label: "Blanc", icon: "⚪", color: "#aaaaaa" }
    Rouge: { label: "Rouge", icon: "🔴", color: "#e84444" }
visible_in: [morning, evening]
weekly_aggregation: none
ai_insight_policy: optional
```

### 40.8 Weather (composite)

```yaml
field_id: weather_main
label: "Météo"
icon: "🌤️"
category_id: weather
provider_type: weather
provider_config:
  source_entity_id: sensor.openmeteo
  source_format: structured_attributes
  hourly_attribute_path: hourly
  daily_attribute_path: daily
  current_attribute_path: current
visible_in: [morning, evening, weekly]
ai_insight_policy: required  # always have AI synthesize weather
```

### 40.9 Daily electricity consumption

```yaml
field_id: elec_daily
label: "Électricité"
icon: "🔌"
category_id: home
provider_type: cumulative
provider_config:
  entity_id: sensor.linky_daily_total
  reset_hour: 0
unit: kWh
direction_preference: lower_is_better
comparisons:
  - { type: yesterday }
  - { type: rolling_avg, window_days: 14 }
  - { type: same_week_last_year }
anomaly_detection:
  mode: pct_change_vs_rolling_avg
  pct: 50
  window_days: 14
visible_in: [morning, evening, weekly]
weekly_aggregation: sum
ai_insight_policy: optional
```

---

## 41. Appendix: ABCs / interfaces (Python code stubs)

(Reproducing key ABCs in one place for quick reference. Detailed in their respective sections.)

```python
# providers/base.py
class FieldProvider(ABC):
    provider_type: str
    def __init__(self, hass, config): ...
    @abstractmethod async def get_current_value(self, logical_date: date) -> FieldValue: ...
    @abstractmethod async def get_value_for_date(self, target_date: date) -> FieldValue: ...
    @abstractmethod async def get_history(self, start: date, end: date) -> dict[date, FieldValue]: ...
    @classmethod @abstractmethod def get_config_schema(cls) -> vol.Schema: ...
    @classmethod def detect_from_entity(cls, hass, entity_id: str) -> float: return 0.0
    @abstractmethod def validate_config(self) -> list[str]: ...

# ai/base.py
class AIProvider(ABC):
    provider_type: str
    def __init__(self, hass, config): ...
    @abstractmethod async def generate(self, prompt: str, language: str, max_tokens: int = 2000) -> AIResult: ...
    @abstractmethod async def validate_credentials(self) -> bool: ...

# logical_day/base.py
class LogicalDayStrategy(ABC):
    strategy_type: str
    def __init__(self, hass, config): ...
    @abstractmethod async def get_logical_date(self, now: datetime) -> tuple[date, int]: ...
    @classmethod @abstractmethod def get_config_schema(cls) -> vol.Schema: ...
    @abstractmethod def validate_config(self) -> list[str]: ...

# reports/base.py
class ReportBuilder(ABC):
    report_type: str
    def __init__(self, hass, coordinator): ...
    @abstractmethod async def build(self, logical_date: date) -> dict: ...
```

---

## 42. Appendix: Frontend type stubs

```typescript
// src/types.ts (matches Section 15 canonical JSON)

export interface CanonicalBrief {
  schema_version: number;
  meta: BriefMeta;
  alerts: Alert[];
  categories: Category[];
  ai_output: AIOutput;
  ha_health: HAHealth;
  previous_briefs_refs: string[];
}

export interface BriefMeta {
  instance_id: string;
  instance_name: string;
  report_type: "morning" | "evening" | "weekly";
  language: string;
  generated_at: string;
  calendar_date: string;
  logical_date: string;
  logical_day_strategy: string;
  logical_day_offset: number;
  ai_status: "ok" | "degraded" | "disabled";
  ai_provider: string | null;
  ai_error: string | null;
  duration_ms: number;
  _truncated?: boolean;
}

export interface Alert {
  severity: "critical" | "warning" | "info";
  source: string;
  field_id: string | null;
  message: string;
  raw_value: number | null;
  threshold: number | null;
}

export interface Category {
  id: string;
  label: string;
  icon: string;
  order: number;
  display_when_empty: boolean;
  fields: Field[];
}

export interface Field {
  id: string;
  label: string;
  icon: string;
  order: number;
  provider_type: string;
  value: FieldValue;
  extra: Record<string, any>;
  comparisons: Comparison[];
  anomaly: AnomalyResult | null;
  sparkline_data: number[];
  direction_preference: "higher_is_better" | "lower_is_better" | "neutral";
}

export interface FieldValue {
  raw: number | string | null;
  formatted: string;
  unit: string | null;
  stale: boolean;
  stale_reason: string | null;
  as_of: string | null;
}

export interface Comparison {
  type: string;
  window_days: number | null;
  value: number | null;
  formatted: string;
  delta: number | null;
  delta_formatted: string;
  direction: "up" | "down" | "flat";
  interpretation: "improvement" | "worsening" | "neutral";
  status: "ok" | "partial" | "insufficient_history" | "unreliable" | "not_applicable";
  days_used: number | null;
}

export interface AnomalyResult {
  detected: boolean;
  severity: "info" | "warning" | "critical";
  mode: string;
  message: string;
  raw_value: number;
  threshold: number;
}

export interface AIOutput {
  category_insights: Record<string, string>;
  weather_synthesis: string;
  verdict: string;
}

export interface HAHealth {
  status: "ok" | "warning" | "critical";
  alerts: any[];
  data: {
    cpu_pct: number;
    ram_pct: number;
    db_size_mib: number;
  };
}

export interface MorningBriefCardConfig {
  type: "custom:morning-brief-card";
  entity: string;
  compact_mode?: boolean;
  show_categories?: string[];
  hide_fields?: string[];
  show_history_nav?: boolean;
  show_ai_sections?: boolean;
  show_alerts?: boolean;
  show_weather?: boolean;
  show_footer?: boolean;
  theme_override?: string;
}
```

---

## 43. Final operating rules for the implementing agent

These rules apply to YOU (Claude Code) while implementing this spec.

1. **Read this entire document before writing any code.**
2. **Execute Section 2 (memory files) before Section 3 (scaffolding) before any other work.**
3. **At the start of every session: read the CLAUDE.md of the repo you're working in. Summarize state to confirm context loaded.**
4. **At the end of every session: execute Section 38 ritual.**
5. **Never invent decisions outside this spec.** If something is ambiguous, ASK the user OR log in `CLAUDE.md > Open questions`.
6. **Never write user-facing strings outside translation files.**
7. **Never write a file > 300 lines without `# rationale:` header.**
8. **Never use `last_updated` for event detection** (Gotcha G1).
9. **Never index timeseries by position** (Gotcha G3).
10. **Never propagate exceptions to the coordinator.** Always log + sane fallback.
11. **Write tests as you go.** Don't accumulate test debt.
12. **Commit small.** One logical unit per commit. Conventional commit format.
13. **Update `PROGRESS.md` after every commit.**
14. **If you find yourself doing something not in this spec**, STOP and ask.

---

## Begin

When this document has been fully read, acknowledge by:
1. Confirming you've read all 43 sections.
2. Executing Section 2 (create memory files in both repo directories, even though the repos themselves don't exist yet — create the directories first).
3. Executing Section 3 (scaffold the two repo trees with stub files).
4. Then start Phase 1 of Section 36.

End.
