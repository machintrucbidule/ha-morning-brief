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
- [x] history/lts.py
- [x] history/short_term.py
- [x] history/event_detector.py
- [x] history/hybrid.py
- [x] history/__init__.py (public exports)
- [x] Tests: LTS only, short-term only, mix, gaps, conflicts

## Phase 3 — Providers
- [x] providers/base.py + providers/__init__.py (registry + factory)
- [x] providers/instantaneous.py + tests
- [x] providers/cumulative.py + tests
- [x] providers/manual.py + tests
- [x] providers/state.py + tests
- [x] providers/event_based.py + tests
- [x] providers/duration.py + tests
- [x] providers/calendar.py + tests
- [x] providers/weather.py + tests

## Phase 4 — Logical day & triggers
- [x] logical_day/base.py + __init__.py (registry + factory)
- [x] logical_day/fixed_cutoff.py + tests
- [x] logical_day/sleep_sensor.py + tests
- [x] logical_day/manual.py + tests
- [x] triggers/schedule.py
- [x] triggers/sensor_based.py
- [x] Tests for triggers (mocked HA scheduler)

## Phase 5 — Availability gate & comparisons & anomaly
- [x] compute/availability.py + tests
- [x] compute/comparisons.py (all 8 types) + tests
- [x] compute/anomaly.py (3 modes) + tests
- [x] compute/__init__.py public exports

## Phase 6 — AI layer
- [x] ai/base.py (AIProvider ABC)
- [x] ai/disabled.py
- [x] ai/retry.py + tests
- [x] ai/ha_ai_task.py + tests
- [x] ai/anthropic_direct.py + tests
- [x] ai/openai_direct.py + tests
- [x] ai/prompt_template.py + tests
- [x] ai/__init__.py (registry + factory) + tests
- [x] prompts/morning_v1.txt, evening_v1.txt, weekly_v1.txt

## Phase 7 — Reports & canonical JSON
- [x] reports/base.py + __init__.py (registry + factory)
- [x] reports/canonical.py
- [x] reports/morning.py
- [x] reports/evening.py
- [x] reports/weekly.py
- [x] rendering/markdown.py
- [x] rendering/notification_short.py
- [x] Tests: canonical, morning, evening, weekly

## Phase 8 — Config flow & subentries
- [x] config_flow.py (6 steps)
- [x] options_flow/{general,logical_day,trigger,notification,persistence,reorder,advanced}.py
- [x] options_flow/__init__.py (main menu + step methods)
- [x] subentries/field/schema.py + flow.py (7-step add/edit)
- [x] subentries/category/flow.py (single step)
- [x] subentries/__init__.py (registry)
- [x] Translations populated EN+FR (133 keys parity)
- [x] Tests: config flow happy paths + validation errors

## Phase 9 — Services, entities, events
- [x] services.py + services.yaml (8 services)
- [x] sensor.py (main + status, with truncation D18/G13)
- [x] button.py (generate + preview)
- [x] Coordinator generation pipeline + events (morning_brief_generated, morning_brief_ai_failed)
- [x] __init__.py wiring (platforms + services + coordinator setup)
- [x] End-to-end test: tests/test_e2e_morning.py

## Phase 10 — Frontend card
(See morning-brief-card/PROGRESS.md.)

## Phase 11 — Docs & blueprints & examples
- [x] README.md (20 sections per Section 31)
- [x] docs/architecture.md
- [x] docs/providers.md
- [x] docs/triggers.md
- [x] docs/ai_providers.md
- [x] docs/multilanguage.md
- [x] docs/examples/lovelace_basic.yaml
- [x] docs/examples/lovelace_compact.yaml
- [x] docs/examples/automation_level3_external_trigger.yaml
- [x] docs/examples/full_config_export.yaml
- [x] blueprints/automation/morning_brief/trigger_on_wake.yaml
- [x] blueprints/automation/morning_brief/trigger_on_schedule.yaml
- [x] CHANGELOG.md
- [x] info.md

## Phase 12 — Polish & release prep
- [x] Full test suite green (299 passed, 0 skipped on CI)
- [x] mypy --strict clean (CI)
- [x] ruff check clean (CI)
- [x] HACS validation passes (8/8)
- [x] Coverage report enabled in CI (pytest --cov, ≥70% global floor)
- [x] preview.png placeholder generated in docs/img/
- [x] MORNING_BRIEF_SPEC.md retained in this repo; removed from card repo per release decision
- [x] CLAUDE.md + PROGRESS.md updated to reflect v1.0.0-rc.1 state
- [x] Tag v1.0.0-rc.1 (release candidate)
- [x] Tag v1.0.0-rc.2 (hotfix: OptionsFlow.config_entry read-only on HA ≥ 2024.12)
- [x] Tag v1.0.0-rc.3 (live-HA UX pass: menu labels, pre-fill, selectors, conditional flow split, device_info, etc. — see CHANGELOG). **CAUTION: rc.3 itself shipped broken code — use rc.4 instead.**
- [x] Tag v1.0.0-rc.4 (hotfix: 4 CI errors that I let slip through rc.3 by tagging before waiting for CI green; G21 added to prevent recurrence)
- [x] Tag v1.0.0-rc.5 (live-HA UX pass #3: subentry buttons wiring G22, options picker→param split + factorisation _form_schemas.py, radio buttons mode=LIST, view default prompt, deferred back-nav)
- [x] Tag v1.0.0-rc.6 (live-HA UX pass #4: HACS hide_default_branch G24, subentry button labels + entry_type G23, subentry reconfigure G25, field schema rewritten with EntitySelector/AttributeSelector everywhere, copy_from shows instance names, 12 selector translation blocks, test_translations_completeness CI check)
- [x] Tag v1.0.0-rc.7 (live-HA UX pass #5: ROOT-CAUSE MappingProxyType bug G27 — fixes empty dropdowns + reorder + attach_subentries simultaneously; copy_from really copies subentries now; persistent_notification feedback after generate/preview; L1/L2/L3 → user-friendly names; awake_state has data_description hints; provider_type descriptions clarified; commit-discipline G26 to fix HACS update SHA)
- [ ] Tag v1.0.0 (after user validates: dropdowns + reorder show items, copy_from works, generate/preview show notifications, card renders end-to-end)
