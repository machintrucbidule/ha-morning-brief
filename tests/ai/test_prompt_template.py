"""Tests for ai/prompt_template.py (Section 13.7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from jinja2 import UndefinedError

from custom_components.morning_brief.ai.prompt_template import PromptTemplate


def test_from_source_renders_variables() -> None:
    tmpl = PromptTemplate.from_source("Hello {{ name }}!")
    assert tmpl.render(name="world") == "Hello world!"


def test_strict_undefined_raises_on_missing_variable() -> None:
    """A typo in the template's variable reference should fail loudly."""
    tmpl = PromptTemplate.from_source("Hi {{ missing }}!")
    with pytest.raises(UndefinedError):
        tmpl.render()


async def test_from_file_loads_from_disk(hass: HomeAssistant, tmp_path: Path) -> None:
    f = tmp_path / "t.txt"
    f.write_text("Salut {{ qui }}!", encoding="utf-8")
    tmpl = await PromptTemplate.from_file(hass, f)
    assert tmpl.render(qui="Ivan") == "Salut Ivan!"


async def test_for_report_type_loads_canonical_template(hass: HomeAssistant) -> None:
    """The shipped prompts/morning_v1.txt loads and renders with all spec vars."""
    tmpl = await PromptTemplate.for_report_type(hass, "morning")
    rendered = tmpl.render(
        language="fr",
        data={
            "meta": {
                "logical_date": "2026-05-15",
                "calendar_date": "2026-05-15",
                "logical_day_offset": 0,
            },
        },
        data_json='{"x": 1}',
        user_custom_context=None,
        previous_briefs_json=None,
    )
    assert "fr" in rendered
    assert "2026-05-15" in rendered
    assert "JSON only" in rendered


async def test_all_three_canonical_templates_load(hass: HomeAssistant) -> None:
    """morning/evening/weekly all exist and parse."""
    for report_type in ("morning", "evening", "weekly"):
        tmpl = await PromptTemplate.for_report_type(hass, report_type)
        assert tmpl.source.strip()  # non-empty
