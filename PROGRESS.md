# PROGRESS.md — home-assistant-morning-brief

Live checklist for the integration repo. Updated continuously. Phases mirror Section 36 of `MORNING_BRIEF_SPEC.md`.

## Step 0 — Memory files
- [x] CLAUDE.md
- [x] DECISIONS.md
- [x] PROGRESS.md

## Step 1 — Repo scaffolding
- [x] Root files (README.md stub, CHANGELOG.md, info.md, hacs.json, LICENSE, .gitignore, pyproject.toml)
- [x] .github/workflows stubs (hacs-validate, lint, test)
- [x] docs/ tree (providers, triggers, ai_providers, multilanguage, architecture, img/, examples/)
- [x] blueprints/automation/morning_brief/ tree
- [x] tests/ tree with __init__.py + conftest.py stubs + fixtures + subdirs
- [x] custom_components/morning_brief/ tree (all stub files per Section 3.1)
- [x] custom_components/morning_brief/brand/ placeholder PNG icons (icon, dark_icon, @2x — transparent; user to replace before v1.0.0)

## Phase 1 — Foundation
- [x] manifest.json (HA Core min version, dependencies, subentry types declared)
- [x] const.py (DOMAIN, defaults, enums)
- [x] types.py (TypedDicts, dataclasses)
- [x] exceptions.py
- [x] translations/{en,fr}.json (skeleton)
- [x] coordinator.py (DataUpdateCoordinator subclass)
- [x] store.py (HA Store wrapper, FIFO rotation)
- [x] __init__.py (setup_entry, unload_entry, remove_entry)
- [x] Tests: store rotation

## Phase 2 — History layer
- [ ] history/lts.py
- [ ] history/short_term.py
- [ ] history/event_detector.py
- [ ] history/hybrid.py
- [ ] Tests: LTS only, short-term only, mix, gaps, conflicts

## Phase 3 — Providers
- [ ] providers/base.py + providers/__init__.py (registry + factory)
- [ ] providers/instantaneous.py + tests
- [ ] providers/cumulative.py + tests
- [ ] providers/manual.py + tests
- [ ] providers/state.py + tests
- [ ] providers/event_based.py + tests
- [ ] providers/duration.py + tests
- [ ] providers/calendar.py + tests
- [ ] providers/weather.py + tests

## Phase 4 — Logical day & triggers
- [ ] logical_day/base.py + __init__.py
- [ ] logical_day/fixed_cutoff.py + tests
- [ ] logical_day/sleep_sensor.py + tests
- [ ] logical_day/manual.py + tests
- [ ] triggers/schedule.py
- [ ] triggers/sensor_based.py
- [ ] Tests for triggers (mocked HA scheduler)

## Phase 5 — Availability gate & comparisons & anomaly
- [ ] compute/availability.py + tests
- [ ] compute/comparisons.py (all 8 types) + tests
- [ ] compute/anomaly.py (3 modes) + tests

## Phase 6 — AI layer
- [ ] ai/base.py
- [ ] ai/disabled.py
- [ ] ai/retry.py + tests
- [ ] ai/ha_ai_task.py + tests
- [ ] ai/anthropic_direct.py + tests
- [ ] ai/openai_direct.py + tests
- [ ] ai/prompt_template.py + tests
- [ ] prompts/morning_v1.txt, evening_v1.txt, weekly_v1.txt

## Phase 7 — Reports & canonical JSON
- [ ] reports/base.py + __init__.py
- [ ] reports/canonical.py
- [ ] reports/morning.py
- [ ] reports/evening.py
- [ ] reports/weekly.py
- [ ] rendering/markdown.py
- [ ] rendering/notification_short.py
- [ ] Tests: morning, evening, weekly e2e

## Phase 8 — Config flow & subentries
- [ ] config_flow.py
- [ ] options_flow/general.py, logical_day.py, trigger.py, notification.py, persistence.py, reorder.py, advanced.py
- [ ] options_flow/__init__.py
- [ ] subentries/field/schema.py + flow.py
- [ ] subentries/category/flow.py
- [ ] Populate translations for all flows
- [ ] Tests: config flow happy paths + validation errors

## Phase 9 — Services, entities, events
- [ ] services.py + services.yaml
- [ ] sensor.py
- [ ] button.py
- [ ] Event firing on completion
- [ ] End-to-end test: tests/test_e2e_morning.py

## Phase 10 — Frontend card
(See morning-brief-card/PROGRESS.md.)

## Phase 11 — Docs & blueprints & examples
- [ ] README.md
- [ ] docs/architecture.md
- [ ] docs/providers.md
- [ ] docs/triggers.md
- [ ] docs/ai_providers.md
- [ ] docs/multilanguage.md
- [ ] docs/examples/*.yaml
- [ ] blueprints/automation/morning_brief/trigger_on_wake.yaml
- [ ] blueprints/automation/morning_brief/trigger_on_schedule.yaml
- [ ] CHANGELOG.md
- [ ] info.md, hacs.json finalize

## Phase 12 — Polish & release prep
- [ ] Full test suite green
- [ ] mypy --strict clean
- [ ] ruff check clean
- [ ] HACS validation passes
- [ ] Tag v1.0.0
