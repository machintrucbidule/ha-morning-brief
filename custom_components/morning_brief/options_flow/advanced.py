"""Advanced section schema (Section 20.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

_PROMPT_FILES = {
    "morning": "morning_v1.txt",
    "evening": "evening_v1.txt",
    "weekly": "weekly_v1.txt",
}


def current_prompt_text(report_type: str) -> str:
    """Read the default prompt template that this report_type uses.

    Returns the file content as a string. Called from the executor by
    the options flow's "view_default_prompt" step (sync I/O — never
    call this directly from the event loop).
    """
    fname = _PROMPT_FILES.get(report_type, _PROMPT_FILES["morning"])
    path = Path(__file__).resolve().parent.parent / "prompts" / fname
    try:
        return path.read_text(encoding="utf-8")
    except OSError as err:
        return f"<could not read {fname}: {err}>"


def advanced_schema(initial: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "log_level", default=initial.get("log_level", "INFO")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(_LOG_LEVELS),
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                "prompt_template_override",
                default=initial.get("prompt_template_override", ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT, multiline=True
                )
            ),
            vol.Optional(
                "user_custom_context",
                default=initial.get("user_custom_context", ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT, multiline=True
                )
            ),
            vol.Required(
                "expose_preview_service",
                default=initial.get("expose_preview_service", True),
            ): selector.BooleanSelector(),
        }
    )
