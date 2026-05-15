# Triggers

Each instance configures ONE of three trigger levels (D7). All three ultimately call the same service `morning_brief.generate.<instance>`.

## Level 1 -- `schedule`

Cron-style time + days-of-week.

```yaml
trigger:
  level: schedule
  config:
    time: "07:30"
    days_of_week: [0, 1, 2, 3, 4]  # Mon-Fri (ISO: 0=Mon ... 6=Sun)
```

Simplest. Use if you do not have a sleep sensor.

## Level 2 -- `sensor_based`

State-machine driven by a binary_sensor (typically a sleep sensor) with delay + opt-out shortcut + daily fallback.

```yaml
trigger:
  level: sensor_based
  config:
    trigger_entity_id: binary_sensor.amazfit_is_sleeping
    trigger_to_state: "off"
    delay_minutes: 30
    optout_entities:
      - sensor.etekcity_weight
    fallback_hour: 12
    fallback_active: true
```

How it works:
1. Listen for `trigger_entity_id` reaching `trigger_to_state`.
2. Start a `delay_minutes` countdown.
3. If any `optout_entities` change during the countdown, cancel and fire immediately.
4. Otherwise the countdown elapses and fires.
5. Independent daily check at `fallback_hour`: if no fire today yet, fire once.

The trigger remembers `last_fired_date` so the fallback never double-fires.

## Level 3 -- `external`

No built-in trigger. Write your own automation calling `morning_brief.generate`. Use for advanced cases.

```yaml
alias: Morning brief on first motion
trigger:
  - platform: state
    entity_id: binary_sensor.bedroom_motion
    to: "on"
condition:
  - condition: time
    after: "06:00:00"
    before: "11:00:00"
action:
  - service: morning_brief.generate
    data:
      entry_id: !secret morning_brief_morning_entry_id
      force: false
```

## Blueprints

Two blueprints ship with the integration to make Level 1 / Level 2 trivial to set up:

- `blueprints/automation/morning_brief/trigger_on_wake.yaml`: sleep sensor + delay + opt-outs + fallback hour.
- `blueprints/automation/morning_brief/trigger_on_schedule.yaml`: time + days of week.

To import a blueprint:
1. Settings -> Automations & Scenes -> Blueprints.
2. Import Blueprint.
3. Paste the GitHub raw URL of the YAML file.

Then create a new automation from the blueprint with your selections.
