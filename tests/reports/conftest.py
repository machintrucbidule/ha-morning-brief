"""Shared fixtures + helpers for report-builder tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.morning_brief.ai.base import AIProvider
from custom_components.morning_brief.logical_day.base import LogicalDayStrategy
from custom_components.morning_brief.types import AIResult, FieldValue


def fake_field(**overrides: Any) -> dict[str, Any]:
    """A minimal field config covering an instantaneous numeric sensor."""
    base: dict[str, Any] = {
        "field_id": "weight",
        "label": "Poids",
        "icon": "⚖️",
        "order": 10,
        "category_id": "health",
        "provider_type": "instantaneous",
        "provider_config": {"entity_id": "sensor.weight", "aggregation": "last"},
        "unit": "kg",
        "direction_preference": "lower_is_better",
        "comparisons": [],
        "anomaly_detection": {"mode": "none"},
        "visible_in": ["morning", "evening", "weekly"],
        "weekly_aggregation": "mean",
    }
    base.update(overrides)
    return base


def fake_category(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "health",
        "label": "Santé",
        "icon": "💪",
        "order": 10,
        "display_when_empty": False,
    }
    base.update(overrides)
    return base


def _ok_envelope() -> str:
    return json.dumps(
        {
            "alertes_formulees": [],
            "insights": {"health": "Solid rest."},
            "weather_synthesis": "",
            "verdict": "Looking good — keep it up.",
        }
    )


@pytest.fixture
def fake_coordinator() -> SimpleNamespace:
    """Duck-typed coordinator with sensible defaults for report tests."""
    strategy = MagicMock(spec=LogicalDayStrategy)
    strategy.strategy_type = "fixed_cutoff"

    ai = MagicMock(spec=AIProvider)
    ai.provider_type = "disabled"
    ai.generate = AsyncMock(
        return_value=AIResult(status="ok", content=_ok_envelope(), tokens_used=0)
    )

    template = MagicMock()
    template.render = MagicMock(return_value="rendered prompt")

    return SimpleNamespace(
        entry_id="entry-1",
        instance_name="Brief matinal",
        language="fr",
        fields=[fake_field()],
        categories=[fake_category()],
        logical_day_strategy=strategy,
        ai_provider=ai,
        prompt_template=template,
        previous_briefs_refs=[],
        previous_briefs=[],
        user_custom_context=None,
        weekly_start_day_of_week=0,
    )


def fresh_value(raw: float | str | None = 75.5) -> FieldValue:
    return FieldValue(raw=raw, unit="kg", stale=False, as_of=datetime.now(UTC))
