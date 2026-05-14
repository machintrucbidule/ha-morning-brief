"""Shared pytest fixtures for the morning_brief integration test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # type: ignore[no-untyped-def]
    """Enable loading custom integrations in tests.

    The `enable_custom_integrations` fixture is provided by
    `pytest-homeassistant-custom-component` and lets HA discover the
    `custom_components/morning_brief/` package during tests.
    """
    yield
