# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial repo scaffolding.
- Foundation skeleton: manifest, const, types, exceptions, translations skeleton, coordinator skeleton, store with FIFO rotation, setup_entry / unload_entry, tests for store rotation.
- History layer (Section 10): `history/lts.py` (LTS daily wrapper), `history/short_term.py` (raw + per-day aggregator), `history/event_detector.py` (filter unavailable/unknown, epsilon dedup, debounce), `history/hybrid.py` (LTS-first orchestrator with short-term gap-fill, recorder-retention-aware, D11 status enum). 39 tests covering Section 10.7 scenarios.
- Field providers (Section 8): `FieldProvider` ABC + registry + factory in `providers/`. All 8 V1 provider types implemented: `instantaneous`, `cumulative`, `event_based`, `state`, `duration`, `calendar`, `weather`, `manual`. Each with config schema, `validate_config`, and `detect_from_entity` heuristic. Comprehensive tests including factory + parametrised happy-path for every type.
