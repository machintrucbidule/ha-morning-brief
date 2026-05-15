# Field providers

The integration ships 8 V1 provider types (closed list, D4). Each provider reads one sensor and returns a typed value with consistent semantics for "value of the day" + stale handling.

## Quick decision tree

| Sensor shape | Provider | Notes |
|---|---|---|
| Counter that resets daily (steps, kWh, sleep min) | `cumulative` | Configure `reset_hour`. Uses LTS `change` natively. |
| Continuous numeric (HR, weight, temp) | `instantaneous` | `mean` for daily average, `last` for current state. |
| Sparse events (Wi-Fi scale, manual readings) | `event_based` | Configure `epsilon` + `min_debounce_minutes`. |
| Non-numeric (tariff colour, workday, presence) | `state` | Optional `state_mapping` for label/icon. |
| Time since X (litter, visitor) | `duration` | 3 source types. |
| Upcoming calendar events | `calendar` | Optional `summary_regex`, `window_days`, `max_events`. |
| Composite weather | `weather` | Two source formats (ha_weather / structured_attributes). |
| Manual user-tracked | `manual` | input_number / input_text / input_datetime. |

## `cumulative`

Daily counter -- value = increase between two consecutive resets.

```yaml
provider_type: cumulative
provider_config:
  entity_id: sensor.amazfit_steps
  reset_hour: 0
```

Edge cases:
- Sensor with `state_class=total_increasing` resets to 0 at `reset_hour`.
- If the sensor does not actually reset, the brief logs a warning.
- Reset hour != 0 supported (e.g. 11:00 for some watches).

## `instantaneous`

For sensors meaningful at any moment.

```yaml
provider_type: instantaneous
provider_config:
  entity_id: sensor.amazfit_hr_resting
  aggregation: last  # or "mean"
  window_hours_today: 24
```

Sensors without LTS -- `mean` falls back to live state for today; past dates return `insufficient_history`.

## `event_based`

Sparse-event sensors. `epsilon` filters numerical noise; `min_debounce_minutes` filters rapid bouncing.

```yaml
provider_type: event_based
provider_config:
  entity_id: sensor.etekcity_weight
  epsilon: 0.05
  min_debounce_minutes: 5
```

If no event happened on the logical day, the value carries `stale: true, stale_reason: "no_event_today"` and the most recent prior event value.

## `state`

Non-numeric state. Optional mapping decorates each value with label/icon/colour.

```yaml
provider_type: state
provider_config:
  entity_id: sensor.rte_tempo_current_color
  state_mapping:
    Bleu: { label: "Bleu", icon: "blue", color: "#3478e8" }
    Rouge: { label: "Rouge", icon: "red", color: "#e84444" }
```

Comparisons: only `yesterday`, `same_weekday_last_week`, `same_week_last_year` make sense; the rest return `not_applicable`.

## `duration`

Time since an event. Three source types:
- `input_datetime`: the entity state IS the reference timestamp.
- `sensor_last_changed`: use the sensor `last_changed`.
- `sensor_attribute_datetime`: read a datetime from an attribute.

```yaml
provider_type: duration
provider_config:
  source_type: input_datetime
  entity_id: input_datetime.litter_last_maintenance
  display_unit: days   # auto | days | hours | minutes
```

Future timestamps clamp to 0 with a warning log.

## `calendar`

Read upcoming events from a `calendar.*` entity.

```yaml
provider_type: calendar
provider_config:
  calendar_entity_id: calendar.personal
  summary_regex: "(?i)vet|dentist"
  window_days: 7
  max_events: 1
```

Past dates return empty -- this provider is informational only.

## `weather`

Composite. Two source formats:
- `ha_weather`: native HA `weather.*` entity.
- `structured_attributes`: sensors with `current`/`hourly`/`daily` attribute blocks (Open-Meteo style).

```yaml
provider_type: weather
provider_config:
  source_entity_id: sensor.openmeteo
  source_format: structured_attributes
  hourly_attribute_path: hourly
  daily_attribute_path: daily
  current_attribute_path: current
```

WMO codes are translated to keys (clear, partly_cloudy, rain_light, etc.) in the `extra` block; the card resolves the human label via its own i18n.

## `manual`

Read an `input_*.*` entity. Auto-detects `value_type` from the prefix.

```yaml
provider_type: manual
provider_config:
  entity_id: input_number.mood
  value_type: number
```

## Availability gate (D5, G5)

Orthogonal to provider type. Any field can declare a gate:

```yaml
availability_gate:
  entity_id: binary_sensor.amazfit_is_sleeping
  expected_state: "off"
```

When the gate is unsatisfied (or the gate sensor itself is unavailable), the field value becomes the previous valid day value, tagged `stale: true, stale_reason: "awaiting_availability"` (or `"gate_sensor_unavailable"`).

The gate runs AFTER the provider -- providers know nothing about it.
