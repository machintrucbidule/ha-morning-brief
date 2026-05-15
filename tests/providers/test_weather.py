"""Tests for providers/weather.py (Section 8.7)."""

from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.providers.weather import (
    WMO_KEYS,
    WeatherProvider,
)


async def test_ha_weather_format_extracts_current_and_forecast(hass: HomeAssistant) -> None:
    eid = "weather.home"
    hass.states.async_set(
        eid,
        "sunny",
        {
            "temperature": 22,
            "humidity": 50,
            "wind_speed": 10,
            "wind_bearing": 180,
            "pressure": 1015,
            "forecast": [
                {
                    "condition": "sunny",
                    "templow": 14,
                    "temperature": 25,
                    "precipitation": 0,
                    "precipitation_probability": 5,
                },
                {
                    "condition": "rainy",
                    "templow": 12,
                    "temperature": 20,
                    "precipitation": 5,
                    "precipitation_probability": 80,
                },
            ],
        },
    )
    result = await WeatherProvider(hass, {"source_entity_id": eid}).get_current_value(
        date(2026, 5, 15)
    )
    assert result.stale is False
    assert result.extra["current"]["weather_text"] == "sunny"
    assert result.extra["current"]["temperature"] == 22
    assert result.extra["today"]["temp_max"] == 25
    assert result.extra["tomorrow"]["weather_text"] == "rainy"


async def test_structured_attributes_format_with_dict_of_arrays(
    hass: HomeAssistant,
) -> None:
    eid = "sensor.openmeteo"
    hass.states.async_set(
        eid,
        "ok",
        {
            "current": {
                "weather_code": 3,
                "temperature_2m": 18.5,
                "time": "2026-05-15T12:00:00+00:00",
            },
            "daily": {
                "weather_code": [1, 61, 95],
                "temperature_2m_min": [10, 12, 14],
                "temperature_2m_max": [22, 18, 26],
                "precipitation_sum": [0, 5, 2],
                "precipitation_probability": [10, 80, 50],
            },
        },
    )
    result = await WeatherProvider(
        hass,
        {"source_entity_id": eid, "source_format": "structured_attributes"},
    ).get_current_value(date(2026, 5, 15))
    assert result.extra["current"]["weather_code"] == 3
    assert result.extra["current"]["weather_key"] == WMO_KEYS[3]
    assert result.extra["today"]["temp_max"] == 22
    assert result.extra["tomorrow"]["weather_key"] == WMO_KEYS[61]


async def test_unavailable_source_is_stale(hass: HomeAssistant) -> None:
    hass.states.async_set("weather.home", "unavailable", {})
    result = await WeatherProvider(
        hass, {"source_entity_id": "weather.home"}
    ).get_current_value(date(2026, 5, 15))
    assert result.raw is None
    assert result.stale is True


async def test_missing_entity_is_stale(hass: HomeAssistant) -> None:
    result = await WeatherProvider(
        hass, {"source_entity_id": "weather.nope"}
    ).get_current_value(date(2026, 5, 15))
    assert result.raw is None
    assert result.stale is True


async def test_get_value_for_date_is_always_stale(hass: HomeAssistant) -> None:
    """Past weather is out of V1 scope."""
    result = await WeatherProvider(
        hass, {"source_entity_id": "weather.home"}
    ).get_value_for_date(date(2026, 5, 1))
    assert result.raw is None
    assert result.stale is True


async def test_unknown_wmo_code_yields_none_key(hass: HomeAssistant) -> None:
    """A WMO code that's not in our table → weather_key is None (no crash)."""
    eid = "sensor.openmeteo"
    hass.states.async_set(
        eid,
        "ok",
        {"current": {"weather_code": 999, "temperature_2m": 10}, "daily": {}},
    )
    result = await WeatherProvider(
        hass,
        {"source_entity_id": eid, "source_format": "structured_attributes"},
    ).get_current_value(date(2026, 5, 15))
    assert result.extra["current"]["weather_code"] == 999
    assert result.extra["current"]["weather_key"] is None


def test_detect_from_entity_weather_high_score(hass: HomeAssistant) -> None:
    assert WeatherProvider.detect_from_entity(hass, "weather.home") == 0.95
    assert WeatherProvider.detect_from_entity(hass, "sensor.foo") == 0.0


def test_validate_config_rejects_unknown_format(hass: HomeAssistant) -> None:
    errors = WeatherProvider(
        hass, {"source_entity_id": "weather.home", "source_format": "blob"}
    ).validate_config()
    assert any("source_format" in e for e in errors)
