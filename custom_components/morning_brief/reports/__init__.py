"""Report builders registry + canonical JSON helpers.

Three V1 report types (D12): morning, evening, weekly. See
MORNING_BRIEF_SPEC.md Section 14.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import REPORT_TYPE_EVENING, REPORT_TYPE_MORNING, REPORT_TYPE_WEEKLY
from ..exceptions import ConfigurationError
from .base import ReportBuilder, ResolvedField
from .canonical import build_canonical_json
from .evening import EveningReport
from .morning import MorningReport
from .weekly import WeeklyReport

REPORTS: dict[str, type[ReportBuilder]] = {
    REPORT_TYPE_MORNING: MorningReport,
    REPORT_TYPE_EVENING: EveningReport,
    REPORT_TYPE_WEEKLY: WeeklyReport,
}


def create_report(
    hass: HomeAssistant, report_type: str, coordinator: Any
) -> ReportBuilder:
    """Instantiate the builder for ``report_type``.

    Raises:
        ConfigurationError: when ``report_type`` is not one of D12.
    """
    if report_type not in REPORTS:
        raise ConfigurationError(f"Unknown report_type: {report_type}")
    return REPORTS[report_type](hass, coordinator)


__all__ = [
    "REPORTS",
    "ReportBuilder",
    "ResolvedField",
    "build_canonical_json",
    "create_report",
]
