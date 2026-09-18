"""Tests del rate limiter de IA."""

import pytest

from app.ai.errors import AIRateLimitError
from app.ai.rate_limit import RateLimitedAIService, SlidingWindowRateLimiter
from app.ai.types import AIMessage
from tests.fake_ai import FakeAIService


def test_limiter_allows_up_to_limit() -> None:
    limiter = SlidingWindowRateLimiter(max_calls=2, window_seconds=3600)
    assert limiter.acquire() is True
    assert limiter.acquire() is True
    assert limiter.acquire() is False


def test_limiter_window_resets_after_time() -> None:
    import time

    limiter = SlidingWindowRateLimiter(max_calls=1, window_seconds=0.01)
    assert limiter.acquire() is True
    assert limiter.acquire() is False
    time.sleep(0.02)
    assert limiter.acquire() is True


async def test_rate_limited_service_rejects() -> None:
    limiter = SlidingWindowRateLimiter(max_calls=0, window_seconds=3600)
    service = RateLimitedAIService(FakeAIService(), limiter)
    with pytest.raises(AIRateLimitError):
        await service.complete([AIMessage(role="user", content="x")])


async def test_rate_limited_service_delegates() -> None:
    limiter = SlidingWindowRateLimiter(max_calls=5, window_seconds=3600)
    service = RateLimitedAIService(FakeAIService(["ok"]), limiter)
    result = await service.complete([AIMessage(role="user", content="x")])
    assert result.content == "ok"
