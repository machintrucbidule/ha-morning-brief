# rationale: composite provider that supports two source shapes
# (`weather.*` HA entities and structured-attribute sensors like Open-Meteo)
# plus a WMO-code mapping table. Splitting would scatter the dual-format
# adapter logic and the structured output contract (Section 8.7) across
# files. Keep cohesive.
"""Weather provider (composite).

Reads either a `weather.*` entity (HA's native weather provider integrations)
or a sensor with structured `current` / `hourly` / `daily` attribute blocks
(typical of Open-Meteo-style sensors). Outputs a structured ``extra`` payload
matching the contract in MORNING_BRIEF_SPEC.md Section 8.7.

WMO weather codes are emitted numerically; the card / renderings translate
them to human text via translation files (D20).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import PROVIDER_WEATHER, STALE_NO_DATA
from ..types import FieldValue
from .base import FieldProvider

_LOGGER = logging.getLogger(__name__)

_FORMAT_HA_WEATHER = "ha_weather"
_FORMAT_STRUCTURED = "structured_attributes"
_FORMATS: frozenset[str] = frozenset({_FORMAT_HA_WEATHER, _FORMAT_STRUCTURED})

# Minimal WMO → key mapping. Card / translations resolve the human text.
# (This is a starter subset; extending it is purely a translations task.)
WMO_KEYS: dict[int, str] = {
    0: "clear",
    1: "mainly_clear",
    2: "partly_cloudy",
    3: "overcast",
    45: "fog",
    48: "fog_rime",
    51: "drizzle_light",
    53: "drizzle",
    55: "drizzle_heavy",
    61: "rain_light",
    63: "rain",
    65: "rain_heavy",
    71: "snow_light",
    73: "snow",
    75: "snow_heavy",
    80: "showers_light",
    81: "showers",
    82: "showers_violent",
    95: "thunderstorm",
    96: "thunderstorm_hail_light",
    99: "thunderstorm_hail_heavy",
}


def _read_path(obj: Any, path: str) -> Any:
    """Read a dotted path from a dict/list-of-dict structure. None on miss."""
    if not path:
        return obj
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _wmo_key(code: Any) -> str | None:
    try:
        return WMO_KEYS.get(int(code))
    except (TypeError, ValueError):
        return None


class WeatherProvider(FieldProvider):
    """Composite weather reader."""

    provider_type = PROVIDER_WEATHER

    @property
    def source_entity_id(self) -> str:
        return str(self.config["source_entity_id"])

    @property
    def source_format(self) -> str:
        configured = self.config.get("source_format")
        if configured in _FORMATS:
            return str(configured)
        # Auto-detect: weather.* entities default to ha_weather.
        if self.source_entity_id.startswith("weather."):
            return _FORMAT_HA_WEATHER
        return _FORMAT_STRUCTURED

    def _attr_path(self, key: str, default: str) -> str:
        return str(self.config.get(key, default))

    def _read_attrs(self) -> dict[str, Any]:
        """Read the source entity's attributes; empty dict if unavailable."""
        state = self.hass.states.get(self.source_entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return {}
        return dict(state.attributes)

    def _build_structured(self) -> dict[str, Any]:
        """Spec Section 8.7 output — current / hourly_remaining / today / tomorrow / day_after."""
        attrs = self._read_attrs()
        if not attrs:
            return {}

        if self.source_format == _FORMAT_HA_WEATHER:
            return self._from_ha_weather(attrs)
        return self._from_structured(attrs)

    def _from_ha_weather(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Adapter for native `weather.*` entities (HA core)."""
        forecast = attrs.get("forecast") or []
        state = self.hass.states.get(self.source_entity_id)
        current_text = state.state if state is not None else ""
        current = {
            "weather_code": None,
            "weather_text": current_text,
            "temperature": attrs.get("temperature"),
            "humidity": attrs.get("humidity"),
            "wind_speed": attrs.get("wind_speed"),
            "wind_direction": attrs.get("wind_bearing"),
            "pressure": attrs.get("pressure"),
        }
        days = forecast[:3] if isinstance(forecast, list) else []
        slots = ["today", "tomorrow", "day_after"]
        out: dict[str, Any] = {"current": current, "hourly_remaining": []}
        for slot, day in zip(slots, days, strict=False):
            if not isinstance(day, dict):
                continue
            out[slot] = {
                "weather_code": None,
                "weather_text": day.get("condition", ""),
                "temp_min": day.get("templow"),
                "temp_max": day.get("temperature"),
                "precip_sum": day.get("precipitation"),
                "precip_proba_max": day.get("precipitation_probability"),
            }
        return out

    def _from_structured(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Adapter for sensors carrying `current`/`hourly`/`daily` blocks."""
        wmo_attr = self._attr_path("wmo_code_attribute", "weather_code")
        temp_attr = self._attr_path("temp_attribute", "temperature_2m")
        precip_proba = self._attr_path("precip_proba_attribute", "precipitation_probability")
        precip_sum = self._attr_path("precip_sum_attribute", "precipitation_sum")
        temp_min = self._attr_path("temp_min_attribute", "temperature_2m_min")
        temp_max = self._attr_path("temp_max_attribute", "temperature_2m_max")

        current_block = (
            _read_path(attrs, self._attr_path("current_attribute_path", "current")) or {}
        )
        daily_block = (
            _read_path(attrs, self._attr_path("daily_attribute_path", "daily")) or {}
        )
        hourly_block = (
            _read_path(attrs, self._attr_path("hourly_attribute_path", "hourly")) or {}
        )

        is_dict = isinstance(current_block, dict)
        current_code = current_block.get(wmo_attr) if is_dict else None
        current = {
            "weather_code": current_code,
            "weather_key": _wmo_key(current_code),
            "temperature": current_block.get(temp_attr) if is_dict else None,
            "time": current_block.get("time") if is_dict else None,
        }

        out: dict[str, Any] = {
            "current": current,
            "hourly_remaining": self._slice_hourly(
                hourly_block, temp_attr, wmo_attr, precip_proba
            ),
        }

        # daily block: support either dict-of-arrays or list-of-dicts.
        slots = ("today", "tomorrow", "day_after")
        for offset, slot in enumerate(slots):
            day = self._daily_at(
                daily_block,
                offset,
                wmo_attr,
                temp_min,
                temp_max,
                precip_sum,
                precip_proba,
            )
            if day is not None:
                out[slot] = day
        return out

    @staticmethod
    def _slice_hourly(
        hourly: Any, temp_attr: str, wmo_attr: str, precip_proba: str
    ) -> list[dict[str, Any]]:
        """Slice hourly forecasts from `now` to end-of-local-day."""
        if not isinstance(hourly, dict):
            return []
        times = hourly.get("time") or []
        temps = hourly.get(temp_attr) or []
        codes = hourly.get(wmo_attr) or []
        proba = hourly.get(precip_proba) or []
        out: list[dict[str, Any]] = []
        now = dt_util.now()
        for i, ts in enumerate(times):
            ts_dt = dt_util.parse_datetime(str(ts))
            if ts_dt is None or ts_dt < now or ts_dt.date() != now.date():
                continue
            entry: dict[str, Any] = {
                "time": ts,
                "temperature": temps[i] if i < len(temps) else None,
                "weather_code": codes[i] if i < len(codes) else None,
                "weather_key": _wmo_key(codes[i]) if i < len(codes) else None,
                "precipitation_probability": proba[i] if i < len(proba) else None,
            }
            out.append(entry)
        return out

    @staticmethod
    def _daily_at(
        daily: Any,
        offset: int,
        wmo_attr: str,
        temp_min: str,
        temp_max: str,
        precip_sum: str,
        precip_proba: str,
    ) -> dict[str, Any] | None:
        """Read the `offset`-th daily entry, supporting both shapes."""
        if isinstance(daily, dict):
            try:
                return {
                    "weather_code": daily[wmo_attr][offset],
                    "weather_key": _wmo_key(daily[wmo_attr][offset]),
                    "temp_min": daily[temp_min][offset],
                    "temp_max": daily[temp_max][offset],
                    "precip_sum": daily[precip_sum][offset],
                    "precip_proba_max": daily[precip_proba][offset]
                    if precip_proba in daily
                    else None,
                }
            except (KeyError, IndexError, TypeError):
                return None
        if isinstance(daily, list) and offset < len(daily):
            day = daily[offset]
            if not isinstance(day, dict):
                return None
            return {
                "weather_code": day.get(wmo_attr),
                "weather_key": _wmo_key(day.get(wmo_attr)),
                "temp_min": day.get(temp_min),
                "temp_max": day.get(temp_max),
                "precip_sum": day.get(precip_sum),
                "precip_proba_max": day.get(precip_proba),
            }
        return None

    async def get_current_value(self, logical_date: date) -> FieldValue:
        structured = self._build_structured()
        if not structured:
            return FieldValue(
                raw=None,
                unit=None,
                stale=True,
                stale_reason=STALE_NO_DATA,
                extra={},
            )
        current_text = structured.get("current", {}).get("weather_text") or structured.get(
            "current", {}
        ).get("weather_key", "")
        return FieldValue(raw=current_text, unit=None, extra=structured)

    async def get_value_for_date(self, target_date: date) -> FieldValue:
        # Past weather is out of V1 scope; daily entries past today aren't queryable.
        return FieldValue(
            raw=None, unit=None, stale=True, stale_reason=STALE_NO_DATA, extra={}
        )

    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        out: dict[date, FieldValue] = {}
        cur = start_date
        while cur <= end_date:
            out[cur] = FieldValue(
                raw=None, unit=None, stale=True, stale_reason=STALE_NO_DATA, extra={}
            )
            cur = date.fromordinal(cur.toordinal() + 1)
        return out

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("source_entity_id"): str,
                vol.Optional("source_format"): vol.In(sorted(_FORMATS)),
                vol.Optional("hourly_attribute_path", default="hourly"): str,
                vol.Optional("daily_attribute_path", default="daily"): str,
                vol.Optional("current_attribute_path", default="current"): str,
                vol.Optional("wmo_code_attribute", default="weather_code"): str,
                vol.Optional("temp_attribute", default="temperature_2m"): str,
                vol.Optional(
                    "precip_proba_attribute", default="precipitation_probability"
                ): str,
                vol.Optional("precip_sum_attribute", default="precipitation_sum"): str,
                vol.Optional("temp_min_attribute", default="temperature_2m_min"): str,
                vol.Optional("temp_max_attribute", default="temperature_2m_max"): str,
            }
        )

    @classmethod
    def detect_from_entity(cls, hass: HomeAssistant, entity_id: str) -> float:
        if entity_id.startswith("weather."):
            return 0.95
        return 0.0

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self.config.get("source_entity_id"):
            errors.append("source_entity_id is required")
        fmt = self.config.get("source_format")
        if fmt is not None and fmt not in _FORMATS:
            errors.append(f"source_format must be one of {sorted(_FORMATS)}")
        return errors
