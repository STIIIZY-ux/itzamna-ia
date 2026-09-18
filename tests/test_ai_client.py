"""Tests del cliente OpenAI-compatible."""

import httpx
import pytest

from app.ai.client import OpenAICompatibleAIService
from app.ai.errors import (
    AIInvalidResponseError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
)
from app.ai.types import AIImage, AIMessage
from tests.fake_http import FakeResponse, install_fake_httpx


def _service(**kwargs) -> OpenAICompatibleAIService:
    defaults = {"api_key": "k", "model": "m", "base_url": "https://api.example.com/v1"}
    defaults.update(kwargs)
    return OpenAICompatibleAIService(**defaults)


async def test_complete_success(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        FakeResponse(
            200,
            {
                "choices": [{"message": {"content": "hola"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
        ),
    )
    result = await _service().complete([AIMessage(role="user", content="hi")])
    assert result.content == "hola"
    assert result.model == "m"
    assert result.usage is not None
    assert result.usage.total_tokens == 8


async def test_complete_429_then_success(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        [
            FakeResponse(429, {}),
            FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}),
        ],
    )
    result = await _service(max_retries=2).complete([AIMessage(role="user", content="x")])
    assert result.content == "ok"


async def test_complete_429_exhausted(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, [FakeResponse(429, {}) for _ in range(3)])
    with pytest.raises(AIRateLimitError):
        await _service(max_retries=2).complete([AIMessage(role="user", content="x")])


async def test_complete_5xx_then_success(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        [
            FakeResponse(500, {}),
            FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}),
        ],
    )
    result = await _service(max_retries=2).complete([AIMessage(role="user", content="x")])
    assert result.content == "ok"


async def test_complete_invalid_response(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(200, {"choices": []}))
    with pytest.raises(AIInvalidResponseError):
        await _service().complete([AIMessage(role="user", content="x")])


async def test_complete_http_400(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(400, text="bad request"))
    with pytest.raises(AIProviderError):
        await _service().complete([AIMessage(role="user", content="x")])


async def test_complete_timeout(monkeypatch) -> None:
    class TimeoutClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("httpx.AsyncClient", TimeoutClient)
    with pytest.raises(AITimeoutError):
        await _service().complete([AIMessage(role="user", content="x")])


def test_message_with_image_becomes_data_url() -> None:
    service = _service()
    message = AIMessage(role="user", content="analiza", image=AIImage(data=b"abc", content_type="image/jpeg"))
    payload = service._to_openai_message(message)
    assert payload["role"] == "user"
    assert payload["content"][0] == {"type": "text", "text": "analiza"}
    image_url = payload["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")


def test_message_without_image_is_plain() -> None:
    service = _service()
    payload = service._to_openai_message(AIMessage(role="user", content="hola"))
    assert payload == {"role": "user", "content": "hola"}
