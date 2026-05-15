"""Jinja2 prompt-template loader.

Templates live in `custom_components/morning_brief/prompts/` as plain
text (`morning_v1.txt`, `evening_v1.txt`, `weekly_v1.txt`). They are in
English (D20) and embed the target language as a Jinja variable so the
model knows what to reply in.

See MORNING_BRIEF_SPEC.md Section 13.7.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from jinja2 import StrictUndefined, Template

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptTemplate:
    """Wraps a Jinja2 template; rendering is pure and synchronous."""

    def __init__(self, source: str) -> None:
        """Hold the raw template source so callers can inspect it if needed."""
        self.source = source
        # StrictUndefined surfaces typos as exceptions instead of silent
        # empty strings — important since the model's reply quality
        # depends on every variable being populated.
        self._template = Template(source, undefined=StrictUndefined)

    def render(self, **variables: Any) -> str:
        """Render the template with the given Jinja variables.

        Raises:
            jinja2.UndefinedError: if a referenced variable is missing.
        """
        return self._template.render(**variables)

    @classmethod
    def from_source(cls, source: str) -> PromptTemplate:
        """Build a template from an in-memory string."""
        return cls(source)

    @classmethod
    async def from_file(cls, hass: HomeAssistant, path: Path) -> PromptTemplate:
        """Load a template from disk via the HA executor (R9)."""
        text: str = await hass.async_add_executor_job(path.read_text, "utf-8")
        return cls(text)

    @classmethod
    async def for_report_type(
        cls, hass: HomeAssistant, report_type: str, version: str = "v1"
    ) -> PromptTemplate:
        """Load the canonical template for ``morning|evening|weekly``."""
        path = _PROMPTS_DIR / f"{report_type}_{version}.txt"
        return await cls.from_file(hass, path)
