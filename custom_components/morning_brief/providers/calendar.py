"""Calendar provider.

Reads upcoming events from a `calendar.*` entity via the `calendar.get_events`
service. Optionally filters by a regex on the event summary, returns up to
``max_events`` items in the FieldValue's ``extra``.

This provider is informational — no comparisons (Section 8.6).
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import PROVIDER_CALENDAR, STALE_NO_DATA
from ..types import FieldValue
from .base import FieldProvider

_LOGGER = logging.getLogger(__name__)


def _normalise_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Pick the canonical fields of one calendar event into a stable shape."""
    return {
        "summary": raw.get("summary") or raw.get("message") or "",
        "start": raw.get("start"),
        "end": raw.get("end"),
        "description": raw.get("description") or "",
        "location": raw.get("location") or "",
    }


class CalendarProvider(FieldProvider):
    """Provider for next-N-events listings (e.g. "next dentist", "next vacuum")."""

    provider_type = PROVIDER_CALENDAR

    @property
    def calendar_entity_id(self) -> str:
        return str(self.config["calendar_entity_id"])

    @property
    def summary_regex(self) -> str | None:
        return self.config.get("summary_regex")

    @property
    def window_days(self) -> int:
        return int(self.config.get("window_days", 7))

    @property
    def max_events(self) -> int:
        return int(self.config.get("max_events", 1))

    async def _fetch_events(self) -> list[dict[str, Any]]:
        """Call `calendar.get_events` for [now, now+window_days]."""
        now = dt_util.now()
        end = now + timedelta(days=self.window_days)
        try:
            response = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "entity_id": self.calendar_entity_id,
                    "start_date_time": now.isoformat(),
                    "end_date_time": end.isoformat(),
                },
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 — defensive at the provider boundary
            _LOGGER.exception(
                "calendar.get_events failed for %s", self.calendar_entity_id
            )
            return []

        if not response:
            return []
        # Response shape: {entity_id: {"events": [...]}}
        bucket = response.get(self.calendar_entity_id, {})
        events = bucket.get("events", []) if isinstance(bucket, dict) else []
        if not isinstance(events, list):
            return []

        regex = re.compile(self.summary_regex) if self.summary_regex else None
        normalised: list[dict[str, Any]] = []
        for raw in events:
            if not isinstance(raw, dict):
                continue
            ev = _normalise_event(raw)
            if regex is not None and not regex.search(ev["summary"]):
                continue
            normalised.append(ev)
            if len(normalised) >= self.max_events:
                break
        return normalised

    async def get_current_value(self, logical_date: date) -> FieldValue:
        events = await self._fetch_events()
        if not events:
            return FieldValue(
                raw=None,
                unit=None,
                stale=True,
                stale_reason=STALE_NO_DATA,
                extra={"events": []},
            )
        return FieldValue(
            raw=events[0]["summary"],
            unit=None,
            extra={"events": events},
        )

    async def get_value_for_date(self, target_date: date) -> FieldValue:
        """Past calendar reads aren't meaningful for this informational provider."""
        return FieldValue(
            raw=None,
            unit=None,
            stale=True,
            stale_reason=STALE_NO_DATA,
            extra={"events": []},
        )

    async def get_history(
        self, start_date: date, end_date: date
    ) -> dict[date, FieldValue]:
        out: dict[date, FieldValue] = {}
        cur = start_date
        while cur <= end_date:
            out[cur] = FieldValue(
                raw=None,
                unit=None,
                stale=True,
                stale_reason=STALE_NO_DATA,
                extra={"events": []},
            )
            cur = date.fromordinal(cur.toordinal() + 1)
        return out

    @classmethod
    def get_config_schema(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("calendar_entity_id"): str,
                vol.Optional("summary_regex"): str,
                vol.Optional("window_days", default=7): vol.All(
                    int, vol.Range(min=1, max=365)
                ),
                vol.Optional("max_events", default=1): vol.All(
                    int, vol.Range(min=1, max=20)
                ),
            }
        )

    @classmethod
    def detect_from_entity(cls, hass: HomeAssistant, entity_id: str) -> float:
        if entity_id.startswith("calendar."):
            return 0.95
        return 0.0

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        eid = self.config.get("calendar_entity_id")
        if not eid:
            errors.append("calendar_entity_id is required")
        elif not eid.startswith("calendar."):
            errors.append("calendar_entity_id must be a calendar.* entity")
        regex = self.config.get("summary_regex")
        if regex is not None:
            try:
                re.compile(regex)
            except re.error as err:
                errors.append(f"summary_regex is not a valid regex: {err}")
        return errors
