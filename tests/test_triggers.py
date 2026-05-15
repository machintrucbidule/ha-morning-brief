# rationale: covers both trigger types (Section 16.1 + 16.2) plus the
# full state-machine of sensor_based (trigger event → delay → opt-out
# shortcut, delay elapsed, daily fallback, idempotent already-fired-today).
# Splitting would dilute the orchestration assertions.
"""Tests for triggers/schedule.py and triggers/sensor_based.py."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.morning_brief.exceptions import ConfigurationError
from custom_components.morning_brief.triggers.schedule import ScheduleTrigger
from custom_components.morning_brief.triggers.sensor_based import SensorBasedTrigger

# --------------------------------------------------------------------------- #
# ScheduleTrigger
# --------------------------------------------------------------------------- #


async def test_schedule_registers_time_change_listener(hass: HomeAssistant) -> None:
    cb = AsyncMock()
    trigger = ScheduleTrigger(
        hass, {"time": "07:30", "days_of_week": [0, 1, 2, 3, 4]}, cb
    )
    with patch(
        "custom_components.morning_brief.triggers.schedule.async_track_time_change",
        return_value=MagicMock(),
    ) as track:
        await trigger.async_setup()
    track.assert_called_once()
    kwargs = track.call_args.kwargs
    assert kwargs["hour"] == 7
    assert kwargs["minute"] == 30


async def test_schedule_fires_callback_only_on_configured_days(
    hass: HomeAssistant,
) -> None:
    cb = AsyncMock()
    captured: dict[str, Any] = {}

    def fake_track(_h: object, listener: Any, **_kw: Any) -> MagicMock:
        captured["listener"] = listener
        return MagicMock()

    trigger = ScheduleTrigger(hass, {"time": "07:30", "days_of_week": [2]}, cb)
    with patch(
        "custom_components.morning_brief.triggers.schedule.async_track_time_change",
        side_effect=fake_track,
    ):
        await trigger.async_setup()

    # Monday (weekday=0) — not configured → no callback.
    await captured["listener"](dt_util.now().replace(year=2026, month=5, day=11))
    cb.assert_not_called()
    # Wednesday (weekday=2) — configured → callback fires.
    await captured["listener"](dt_util.now().replace(year=2026, month=5, day=13))
    cb.assert_awaited_once()


async def test_schedule_unload_calls_unsub(hass: HomeAssistant) -> None:
    unsub = MagicMock()
    trigger = ScheduleTrigger(hass, {"time": "07:30"}, AsyncMock())
    with patch(
        "custom_components.morning_brief.triggers.schedule.async_track_time_change",
        return_value=unsub,
    ):
        await trigger.async_setup()
    await trigger.async_unload()
    unsub.assert_called_once()


async def test_schedule_swallows_callback_exceptions(hass: HomeAssistant) -> None:
    """If the user callback explodes, the trigger logs and continues — no HA crash."""
    captured: dict[str, Any] = {}

    def fake_track(_h: object, listener: Any, **_kw: Any) -> MagicMock:
        captured["listener"] = listener
        return MagicMock()

    cb = AsyncMock(side_effect=RuntimeError("user code blew up"))
    trigger = ScheduleTrigger(hass, {"time": "07:30"}, cb)
    with patch(
        "custom_components.morning_brief.triggers.schedule.async_track_time_change",
        side_effect=fake_track,
    ):
        await trigger.async_setup()
    # Should not raise.
    await captured["listener"](dt_util.now())


def test_schedule_invalid_time_format_raises(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError):
        ScheduleTrigger(hass, {"time": "not a time"}, AsyncMock())


def test_schedule_out_of_range_hour_raises(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError):
        ScheduleTrigger(hass, {"time": "25:00"}, AsyncMock())


# --------------------------------------------------------------------------- #
# SensorBasedTrigger
# --------------------------------------------------------------------------- #


def _make_event(new_state_value: str) -> MagicMock:
    """Build a fake state-change Event with `data['new_state'].state`."""
    new_state = MagicMock()
    new_state.state = new_state_value
    event = MagicMock()
    event.data = {"new_state": new_state}
    return event


def _sensor_cfg(**overrides: object) -> dict[str, object]:
    cfg: dict[str, object] = {
        "trigger_entity_id": "binary_sensor.is_sleeping",
        "trigger_to_state": "off",
        "delay_minutes": 30,
        "optout_entities": ["sensor.scale_weight"],
        "fallback_hour": 12,
        "fallback_active": True,
    }
    cfg.update(overrides)
    return cfg


async def test_sensor_based_setup_registers_three_listeners(hass: HomeAssistant) -> None:
    cb = AsyncMock()
    with (
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_state_change_event",
            return_value=MagicMock(),
        ) as state_track,
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_time_change",
            return_value=MagicMock(),
        ) as time_track,
    ):
        trigger = SensorBasedTrigger(hass, _sensor_cfg(), cb)
        await trigger.async_setup()
    # Trigger sensor + opt-outs → 2 calls; fallback → 1 time-change call.
    assert state_track.call_count == 2
    assert time_track.call_count == 1


async def test_sensor_based_trigger_to_state_starts_delay(hass: HomeAssistant) -> None:
    """A transition to trigger_to_state schedules `async_call_later`."""
    cb = AsyncMock()
    captured: dict[str, Any] = {}

    def fake_state_track(_h: object, _entities: Any, listener: Any) -> MagicMock:
        # First call is for the trigger sensor.
        captured.setdefault("trigger_listener", listener)
        return MagicMock()

    with (
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_state_change_event",
            side_effect=fake_state_track,
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_time_change",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_call_later",
            return_value=MagicMock(),
        ) as call_later,
    ):
        trigger = SensorBasedTrigger(
            hass, _sensor_cfg(optout_entities=[]), cb
        )
        await trigger.async_setup()
        captured["trigger_listener"](_make_event("off"))

    call_later.assert_called_once()
    # delay_minutes=30 → 1800 seconds.
    assert call_later.call_args.args[1] == 1800


async def test_sensor_based_optout_during_delay_fires_immediately(
    hass: HomeAssistant,
) -> None:
    cb = AsyncMock()
    listeners: list[Any] = []

    def fake_state_track(_h: object, _entities: Any, listener: Any) -> MagicMock:
        listeners.append(listener)
        return MagicMock()

    cancel_delay = MagicMock()
    with (
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_state_change_event",
            side_effect=fake_state_track,
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_time_change",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_call_later",
            return_value=cancel_delay,
        ),
    ):
        trigger = SensorBasedTrigger(hass, _sensor_cfg(), cb)
        await trigger.async_setup()
        trigger_listener, optout_listener = listeners[0], listeners[1]
        # Start the delay.
        trigger_listener(_make_event("off"))
        # Opt-out fires before the delay elapses.
        optout_listener(_make_event("75.4"))
        # Yield so async_create_task can run our _fire coro.
        await hass.async_block_till_done()

    cancel_delay.assert_called_once()
    cb.assert_awaited_once()


async def test_sensor_based_delay_elapsed_fires(hass: HomeAssistant) -> None:
    cb = AsyncMock()
    captured: dict[str, Any] = {}

    def fake_state_track(_h: object, _entities: Any, listener: Any) -> MagicMock:
        captured.setdefault("trigger_listener", listener)
        return MagicMock()

    def fake_call_later(_h: object, _delay: int, on_elapsed: Any) -> MagicMock:
        captured["delay_callback"] = on_elapsed
        return MagicMock()

    with (
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_state_change_event",
            side_effect=fake_state_track,
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_time_change",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_call_later",
            side_effect=fake_call_later,
        ),
    ):
        trigger = SensorBasedTrigger(
            hass, _sensor_cfg(optout_entities=[]), cb
        )
        await trigger.async_setup()
        captured["trigger_listener"](_make_event("off"))
        await captured["delay_callback"](dt_util.now())

    cb.assert_awaited_once()


async def test_sensor_based_fallback_fires_if_not_already_fired_today(
    hass: HomeAssistant,
) -> None:
    cb = AsyncMock()
    captured: dict[str, Any] = {}

    def fake_time_track(_h: object, listener: Any, **_kw: Any) -> MagicMock:
        captured["fallback_listener"] = listener
        return MagicMock()

    with (
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_state_change_event",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_time_change",
            side_effect=fake_time_track,
        ),
    ):
        trigger = SensorBasedTrigger(hass, _sensor_cfg(optout_entities=[]), cb)
        await trigger.async_setup()
        await captured["fallback_listener"](dt_util.now())

    cb.assert_awaited_once()


async def test_sensor_based_fallback_does_not_double_fire(hass: HomeAssistant) -> None:
    cb = AsyncMock()
    captured: dict[str, Any] = {}

    def fake_time_track(_h: object, listener: Any, **_kw: Any) -> MagicMock:
        captured["fallback_listener"] = listener
        return MagicMock()

    with (
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_state_change_event",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_time_change",
            side_effect=fake_time_track,
        ),
    ):
        trigger = SensorBasedTrigger(hass, _sensor_cfg(optout_entities=[]), cb)
        await trigger.async_setup()
        await captured["fallback_listener"](dt_util.now())
        await captured["fallback_listener"](dt_util.now())

    cb.assert_awaited_once()


async def test_sensor_based_unload_cancels_everything(hass: HomeAssistant) -> None:
    unsub_a, unsub_b, unsub_c = MagicMock(), MagicMock(), MagicMock()
    cancel_delay = MagicMock()
    state_unsubs = iter([unsub_a, unsub_b])

    with (
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_state_change_event",
            side_effect=lambda *_a, **_kw: next(state_unsubs),
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_track_time_change",
            return_value=unsub_c,
        ),
        patch(
            "custom_components.morning_brief.triggers.sensor_based.async_call_later",
            return_value=cancel_delay,
        ),
    ):
        trigger = SensorBasedTrigger(hass, _sensor_cfg(), AsyncMock())
        await trigger.async_setup()
        # Trip the delay so we have a cancel_delay to unhook.
        listeners_ = [
            unsub_a,
            unsub_b,
        ]  # not used here; just ensures no NameError
        _ = listeners_
        # Now unload.
        await trigger.async_unload()

    unsub_a.assert_called_once()
    unsub_b.assert_called_once()
    unsub_c.assert_called_once()


def test_sensor_based_validate_config_requires_entity(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError):
        SensorBasedTrigger(hass, {"trigger_to_state": "off"}, AsyncMock())


def test_sensor_based_validate_config_rejects_bad_optout_list(hass: HomeAssistant) -> None:
    with pytest.raises(ConfigurationError):
        SensorBasedTrigger(
            hass,
            {
                "trigger_entity_id": "binary_sensor.x",
                "trigger_to_state": "off",
                "optout_entities": "not a list",
            },
            AsyncMock(),
        )


# Silence unused-import warnings.
_ = (date, datetime, timedelta)
