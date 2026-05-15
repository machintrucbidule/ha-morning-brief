"""Evening report builder (Section 14.3).

Identical pipeline to the morning report — same field-resolution
helpers, same AI dispatch, same canonical assembly — but filtered to
``visible_in: evening`` and always called with ``cal_offset = 0`` per
spec (the day "ending" is today's calendar day).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..const import REPORT_TYPE_EVENING
from .morning import MorningReport


class EveningReport(MorningReport):
    """Same orchestration as morning, different report_type filter."""

    report_type = REPORT_TYPE_EVENING

    async def build(self, logical_date: date, cal_offset: int = 0) -> dict[str, Any]:
        # Section 14.3: cal_offset is always 0 for the evening report.
        del cal_offset
        return await super().build(logical_date, cal_offset=0)
