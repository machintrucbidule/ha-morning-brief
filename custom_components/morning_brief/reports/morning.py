"""Morning report builder (Section 14.2).

Iterates the instance's fields filtered to ``visible_in: morning``,
resolves each via the shared pipeline, dispatches to the AI provider,
and packages the canonical JSON (Section 15).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date
from typing import Any

from ..ai import generate_with_retry
from ..const import (
    AI_STATUS_DEGRADED,
    AI_STATUS_DISABLED,
    AI_STATUS_OK,
    REPORT_TYPE_MORNING,
)
from .base import ReportBuilder, ResolvedField
from .canonical import build_canonical_json

_LOGGER = logging.getLogger(__name__)


def _visible_for(fields: list[dict[str, Any]], report_type: str) -> list[dict[str, Any]]:
    """Return only the fields whose ``visible_in`` list contains ``report_type``."""
    out: list[dict[str, Any]] = []
    for f in fields:
        visible = f.get("visible_in") or []
        if report_type in visible:
            out.append(f)
    return out


async def _call_ai(
    coordinator: Any, prompt: str, language: str
) -> tuple[dict[str, Any] | None, str, str | None]:
    """Run the configured AI provider with retry.

    Returns ``(envelope_or_none, ai_status, ai_error)``.
    """
    provider = getattr(coordinator, "ai_provider", None)
    if provider is None:
        return None, AI_STATUS_DISABLED, None
    result = await generate_with_retry(provider, prompt, language)
    if result.status != "ok" or result.content is None:
        return None, AI_STATUS_DEGRADED, result.error_message
    try:
        envelope = json.loads(result.content)
    except (json.JSONDecodeError, ValueError) as err:
        return None, AI_STATUS_DEGRADED, str(err)
    if provider.provider_type == "disabled":
        return envelope, AI_STATUS_DISABLED, None
    return envelope, AI_STATUS_OK, None


class MorningReport(ReportBuilder):
    """Flagship morning brief."""

    report_type = REPORT_TYPE_MORNING

    async def build(self, logical_date: date, cal_offset: int = 0) -> dict[str, Any]:
        """Build the canonical morning JSON for ``logical_date``."""
        start = time.monotonic()
        coordinator = self.coordinator
        fields = _visible_for(
            list(getattr(coordinator, "fields", []) or []), self.report_type
        )

        resolved: list[ResolvedField] = []
        for field_config in fields:
            try:
                rf = await self._resolve_field(field_config, logical_date)
            except Exception:  # noqa: BLE001 — never let one bad field crash the brief
                _LOGGER.exception(
                    "Field %s failed to resolve — skipped",
                    field_config.get("field_id"),
                )
                continue
            resolved.append(rf)

        # Render the prompt and dispatch AI.
        prompt = await self._render_prompt(
            coordinator, resolved, logical_date, cal_offset
        )
        ai_envelope, ai_status, ai_error = await _call_ai(
            coordinator, prompt, language=str(getattr(coordinator, "language", "en"))
        )

        duration_ms = int((time.monotonic() - start) * 1000)
        provider = getattr(coordinator, "ai_provider", None)
        return build_canonical_json(
            instance_id=str(getattr(coordinator, "entry_id", "")) or str(uuid.uuid4()),
            instance_name=str(getattr(coordinator, "instance_name", "")),
            report_type=self.report_type,
            language=str(getattr(coordinator, "language", "en")),
            logical_date=logical_date,
            cal_offset=cal_offset,
            logical_day_strategy=str(
                getattr(
                    getattr(coordinator, "logical_day_strategy", None),
                    "strategy_type",
                    "",
                )
            ),
            fields_resolved=resolved,
            categories=list(getattr(coordinator, "categories", []) or []),
            ai_envelope=ai_envelope,
            ai_provider=provider.provider_type if provider else None,
            ai_status=ai_status,
            ai_error=ai_error,
            previous_briefs_refs=list(
                getattr(coordinator, "previous_briefs_refs", []) or []
            ),
            duration_ms=duration_ms,
        )

    async def _render_prompt(
        self,
        coordinator: Any,
        resolved: list[ResolvedField],
        logical_date: date,
        cal_offset: int,
    ) -> str:
        """Render the Jinja2 prompt with the partial canonical payload.

        The prompt embeds a JSON dump of the just-built data so the model
        sees exactly what the user will see.
        """
        template = getattr(coordinator, "prompt_template", None)
        if template is None:
            return ""
        language = str(getattr(coordinator, "language", "en"))
        partial = build_canonical_json(
            instance_id=str(getattr(coordinator, "entry_id", "")),
            instance_name=str(getattr(coordinator, "instance_name", "")),
            report_type=self.report_type,
            language=language,
            logical_date=logical_date,
            cal_offset=cal_offset,
            logical_day_strategy=str(
                getattr(
                    getattr(coordinator, "logical_day_strategy", None),
                    "strategy_type",
                    "",
                )
            ),
            fields_resolved=resolved,
            categories=list(getattr(coordinator, "categories", []) or []),
            ai_envelope=None,
            ai_provider=None,
        )
        return template.render(
            language=language,
            data=partial,
            data_json=json.dumps(partial, default=str, ensure_ascii=False),
            user_custom_context=getattr(coordinator, "user_custom_context", None),
            previous_briefs_json=json.dumps(
                getattr(coordinator, "previous_briefs", []) or [],
                default=str,
                ensure_ascii=False,
            ),
        )
