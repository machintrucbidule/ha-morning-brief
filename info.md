# Morning Brief

A configurable, AI-narrated daily / evening / weekly brief integration for Home Assistant.

- 8 sensor reading strategies (cumulative, instantaneous, event-based, state, duration, calendar, weather, manual)
- 8 comparison types (yesterday, last week, rolling averages, year-over-year, trend, target, ...)
- 4 AI provider backends (HA AI Task, Anthropic direct, OpenAI direct, disabled)
- 3 logical-day strategies (fixed cutoff, sleep sensor, manual)
- 3 trigger levels (schedule, sensor-based with delay+optouts, external)
- Per-field anomaly detection (z-score, static threshold, % change)
- Persists last N briefs with FIFO rotation
- Multilingual (FR + EN at launch)

Companion Lovelace card distributed separately as `morning-brief-card`.
