"""Shared fixtures for history-layer tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_recorder() -> MagicMock:
    """A stand-in for `homeassistant.components.recorder.get_instance(hass)`.

    Tests patch `get_instance` to return this mock. Its
    `async_add_executor_job` simply runs the callable inline (no real
    executor pool), so the synchronous recorder helpers we're mocking
    return their canned data directly.
    """
    rec = MagicMock()

    async def run_inline(fn: Any, *args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    rec.async_add_executor_job = run_inline
    rec.keep_days = 10
    return rec
