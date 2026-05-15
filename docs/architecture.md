# Architecture overview

A user-facing distillation of `MORNING_BRIEF_SPEC.md`. For the full spec, see the file at the repo root.

## High-level data flow

```
Triggers (L1/L2/L3)
   |
   v
Coordinator.async_generate_brief
   |
   +--> Providers (8 types) --> History (LTS + short-term)
   +--> Compute (gate + comparisons + anomaly)
   +--> AI provider (with retry)
   |
   v
ReportBuilder --> canonical JSON (Section 15)
   |
   +--> BriefStore (FIFO rotation)
   +--> Event bus (morning_brief_generated)
   +--> sensor.morning_brief_<slug> attributes (truncated past 16 KB)
   +--> card / markdown / notification renderings
```

## Subsystems

- **Providers** (8 types, closed list per D4). Read sensor values for one logical date. See `docs/providers.md` and Spec Section 8.
- **History** -- LTS + short-term hybrid (D10, G7). Date-indexed, retention-aware. Spec Section 10.
- **Compute** -- availability gate (D5) + 8 comparisons (D14) + 3 anomaly modes (D15). Spec Sections 9, 11, 12.
- **AI** -- 4 backends (D8); `disabled` is the graceful-degradation fallback (D9). See `docs/ai_providers.md`.
- **Reports** -- 3 report types (D12) producing the canonical JSON.
- **Storage** -- FIFO rotation, last N briefs (D16). Spec Section 17.
- **Config flow** -- 6-step instance creation, 8-section options, 2 subentry types (D3).
- **Services + entities + events** -- 8 services, 2 sensors + 2 buttons per instance, 2 bus events. Spec Section 18.

## Single canonical JSON (D17)

The full schema is in Spec Section 15. EVERY consumer -- the card, the markdown fallback, the notification body, any future integration -- reads the same JSON. D17 prohibits an alternative source of truth.

The sensor exposes the canonical JSON in its attributes, with a 16 KB truncation fallback (D18/G13). When truncated, the card calls `morning_brief.get_last_brief` to fetch the full payload over the WebSocket.

## Two repos (D1)

- `ha-morning-brief` -- Python custom_component (this repo).
- `ha-morning-brief-card` -- TypeScript/Lit Lovelace card.

Independent versioning, independent CI. They share only the canonical JSON schema.
