"""DataUpdateCoordinator for the morning_brief integration.

Phase 9 wires the real generation pipeline:
- `async_generate_brief()` runs the logical-day → ReportBuilder → BriefStore
  → event-bus → coordinator-data update chain.
- `async_preview_brief()` does the same without persisting or notifying.

Refresh is event-driven (D7) — triggers call `async_request_refresh()` which
routes through `_async_update_data` → `async_generate_brief`.

See MORNING_BRIEF_SPEC.md Sections 14, 17, 18.
"""

from __future__ import annotations

import logging
import uuid as uuid_module
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .ai.base import AIProvider
from .ai.prompt_template import PromptTemplate
from .const import (
    DOMAIN,
    EVENT_AI_FAILED,
    EVENT_BRIEF_GENERATED,
    REPORT_TYPE_MORNING,
)
from .logical_day.base import LogicalDayStrategy
from .rendering import render_markdown, render_notification_short
from .reports import create_report
from .store import BriefStore

_LOGGER = logging.getLogger(__name__)


class MorningBriefCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator that owns one instance's runtime state + generation pipeline."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        store: BriefStore,
    ) -> None:
        """Initialise the coordinator (attributes filled in by ``async_setup_entry``)."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=None,
        )
        self.entry = entry
        self.store = store
        # Attributes the ReportBuilder reads — populated by __init__.py setup.
        self.instance_name: str = str(entry.data.get("instance_name", entry.title))
        self.language: str = str(entry.data.get("language", "en"))
        self.report_type: str = str(entry.data.get("report_type", REPORT_TYPE_MORNING))
        self.fields: list[dict[str, Any]] = []
        self.categories: list[dict[str, Any]] = []
        self.logical_day_strategy: LogicalDayStrategy | None = None
        self.ai_provider: AIProvider | None = None
        self.prompt_template: PromptTemplate | None = None
        self.previous_briefs_refs: list[str] = []
        self.previous_briefs: list[dict[str, Any]] = []
        self.user_custom_context: str | None = None
        self.weekly_start_day_of_week: int = 0

    # The DataUpdateCoordinator API uses `entry_id` from the entry; expose it
    # directly so the ReportBuilder duck-typed access doesn't need to dig into
    # `coordinator.entry.entry_id`.
    @property
    def entry_id(self) -> str:
        """Pass-through to the wrapped config entry's id."""
        return self.entry.entry_id

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Triggers route through here. Always produce a fresh brief."""
        return await self.async_generate_brief(force=False)

    async def async_generate_brief(self, *, force: bool = False) -> dict[str, Any] | None:
        """Run the full pipeline and persist+notify the result.

        Args:
            force: if True, generate even when an identical-logical-date brief
                is already in history.

        Returns:
            The canonical JSON dict, or None if generation failed catastrophically.
        """
        if self.logical_day_strategy is None:
            _LOGGER.warning(
                "Coordinator not fully initialised — skipping generation"
            )
            return None
        now = dt_util.now()
        logical_date, cal_offset = await self.logical_day_strategy.get_logical_date(now)

        if not force:
            latest = await self.store.get_latest()
            if latest and latest.get("logical_date") == logical_date.isoformat():
                self.async_set_updated_data(latest.get("canonical_json"))
                return latest.get("canonical_json")

        # Refresh previous-briefs context for the AI prompt.
        existing = await self.store.list_briefs()
        self.previous_briefs_refs = [b["uuid"] for b in existing[:2]]
        self.previous_briefs = [b.get("canonical_json", {}) for b in existing[:2]]

        try:
            builder = create_report(self.hass, self.report_type, self)
            canonical = await builder.build(logical_date, cal_offset)
        except Exception:  # noqa: BLE001 — D9 / R6 entry-point boundary
            _LOGGER.exception("Brief generation failed")
            return self.data

        brief_uuid = str(uuid_module.uuid4())
        brief = {
            "uuid": brief_uuid,
            "generated_at": canonical["meta"]["generated_at"],
            "report_type": self.report_type,
            "logical_date": canonical["meta"]["logical_date"],
            "canonical_json": canonical,
            "rendered_markdown": render_markdown(canonical),
            "notification_short": render_notification_short(canonical),
        }
        try:
            await self.store.add_brief(brief)
        except Exception:  # noqa: BLE001 — persist failure must not crash the brief
            _LOGGER.exception("Failed to persist brief — continuing")

        ai_status = canonical["meta"].get("ai_status", "ok")
        self.hass.bus.async_fire(
            EVENT_BRIEF_GENERATED,
            {
                "instance_id": self.entry.entry_id,
                "instance_name": self.instance_name,
                "report_type": self.report_type,
                "logical_date": canonical["meta"]["logical_date"],
                "status": ai_status,
                "brief_uuid": brief_uuid,
            },
        )
        if ai_status == "degraded":
            self.hass.bus.async_fire(
                EVENT_AI_FAILED,
                {
                    "instance_id": self.entry.entry_id,
                    "attempt_count": 3,
                    "error_message": canonical["meta"].get("ai_error", ""),
                },
            )

        self.async_set_updated_data(canonical)
        return canonical

    async def async_preview_brief(self) -> dict[str, Any] | None:
        """Run the pipeline without persisting / firing events. Returns the JSON."""
        if self.logical_day_strategy is None:
            return None
        now = dt_util.now()
        logical_date, cal_offset = await self.logical_day_strategy.get_logical_date(now)
        try:
            builder = create_report(self.hass, self.report_type, self)
            return await builder.build(logical_date, cal_offset)
        except Exception:  # noqa: BLE001 — D9 / R6
            _LOGGER.exception("Preview generation failed")
            return None

    def get_last_brief(self) -> dict[str, Any] | None:
        """Return the cached canonical from the last successful refresh."""
        return self.data
