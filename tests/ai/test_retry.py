"""Tests for ai/retry.py (Section 13.6, D8, G14)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.morning_brief.ai.base import AIProvider
from custom_components.morning_brief.ai.retry import generate_with_retry
from custom_components.morning_brief.types import AIResult


def _provider(*results: AIResult) -> MagicMock:
    """Build a mock AIProvider whose generate() yields the canned results in order."""
    prov = MagicMock(spec=AIProvider)
    prov.provider_type = "test"
    prov.generate = AsyncMock(side_effect=list(results))
    return prov


def _ok(content: str = '{"verdict": "ok"}') -> AIResult:
    return AIResult(status="ok", content=content)


def _err(msg: str = "boom") -> AIResult:
    return AIResult(status="error", content=None, error_message=msg)


async def test_success_on_first_attempt_returns_immediately() -> None:
    prov = _provider(_ok())
    with patch(
        "custom_components.morning_brief.ai.retry.asyncio.sleep", AsyncMock()
    ) as sleep:
        r = await generate_with_retry(prov, "prompt", "en", max_attempts=3)
    assert r.status == "ok"
    assert prov.generate.await_count == 1
    sleep.assert_not_called()


async def test_success_on_second_attempt_after_error() -> None:
    prov = _provider(_err(), _ok())
    with patch(
        "custom_components.morning_brief.ai.retry.asyncio.sleep", AsyncMock()
    ) as sleep:
        r = await generate_with_retry(prov, "prompt", "en", max_attempts=3)
    assert r.status == "ok"
    assert prov.generate.await_count == 2
    sleep.assert_awaited_once()  # one back-off between attempts 1 → 2


async def test_invalid_json_response_triggers_retry() -> None:
    """An 'ok' status with non-JSON content counts as a failure for retry."""
    prov = _provider(_ok(content="not json"), _ok(content='{"verdict": "ok"}'))
    with patch("custom_components.morning_brief.ai.retry.asyncio.sleep", AsyncMock()):
        r = await generate_with_retry(prov, "prompt", "en", max_attempts=3)
    assert r.content == '{"verdict": "ok"}'
    assert prov.generate.await_count == 2


async def test_all_attempts_fail_returns_last_failure() -> None:
    prov = _provider(_err("a"), _err("b"), _err("c"))
    with patch("custom_components.morning_brief.ai.retry.asyncio.sleep", AsyncMock()):
        r = await generate_with_retry(prov, "prompt", "en", max_attempts=3)
    assert r.status == "error"
    assert r.error_message == "c"
    assert prov.generate.await_count == 3


async def test_exponential_backoff_uses_base_delay_x_2_pow_n() -> None:
    """60s, 120s, 240s for base=60 and 3 attempts."""
    prov = _provider(_err(), _err(), _err())
    with patch(
        "custom_components.morning_brief.ai.retry.asyncio.sleep", AsyncMock()
    ) as sleep:
        await generate_with_retry(prov, "prompt", "en", max_attempts=3, base_delay_seconds=60)
    # 2 back-offs between 3 attempts: 60, 120
    assert [c.args[0] for c in sleep.await_args_list] == [60, 120]


async def test_zero_max_attempts_returns_synthetic_error() -> None:
    prov = _provider()
    r = await generate_with_retry(prov, "prompt", "en", max_attempts=0)
    assert r.status == "error"
    assert r.error_message == "zero_attempts_configured"
