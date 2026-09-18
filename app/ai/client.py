"""Cliente OpenAI-compatible (funciona con OpenAI, Groq, OpenRouter, Ollama...)."""

from __future__ import annotations

import asyncio
import base64
import logging
import time

import httpx

from .base import AIService
from .errors import (
    AIInvalidResponseError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
)
from .types import AIMessage, AIResult, AIUsage

logger = logging.getLogger(__name__)


class OpenAICompatibleAIService(AIService):
    """Implementación de ``AIService`` sobre una API estilo chat/completions."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        max_tokens: int = 1024,
        provider_name: str = "openai-compatible",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._max_tokens = max_tokens
        self._provider = provider_name

    async def complete(
        self,
        messages: list[AIMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIResult:
        payload: dict = {
            "model": self._model,
            "messages": [self._to_openai_message(m) for m in messages],
            "max_tokens": max_tokens or self._max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        url = f"{self._base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

        started = time.monotonic()
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as client:
                    response = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise AITimeoutError("timeout del proveedor de IA") from exc
            except httpx.HTTPError as exc:
                raise AIProviderError(f"error de red hacia el proveedor: {exc}") from exc

            if response.status_code == 429:
                if attempt < self._max_retries:
                    await asyncio.sleep(2.0 * (2**attempt))
                    continue
                raise AIRateLimitError("límite de cuota del proveedor")
            if response.status_code >= 500:
                if attempt < self._max_retries:
                    await asyncio.sleep(2.0 * (2**attempt))
                    continue
                raise AIProviderError(f"error 5xx del proveedor: {response.status_code}")
            if response.status_code >= 400:
                raise AIProviderError(f"error {response.status_code}: {response.text[:200]}")

            try:
                data = response.json()
            except ValueError as exc:
                raise AIInvalidResponseError("respuesta no-JSON") from exc

            return self._parse(data, started)

        raise AIProviderError("agotados los reintentos")

    def _parse(self, data: dict, started: float) -> AIResult:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIInvalidResponseError("respuesta sin content") from exc

        usage_raw = data.get("usage") or {}
        usage = AIUsage(
            prompt_tokens=usage_raw.get("prompt_tokens"),
            completion_tokens=usage_raw.get("completion_tokens"),
            total_tokens=usage_raw.get("total_tokens"),
        )
        return AIResult(
            content=content,
            provider=self._provider,
            model=self._model,
            usage=usage,
            latency_ms=(time.monotonic() - started) * 1000,
        )

    def _to_openai_message(self, message: AIMessage) -> dict:
        if message.image is None:
            return {"role": message.role, "content": message.content}
        encoded = base64.b64encode(message.image.data).decode("ascii")
        data_url = f"data:{message.image.content_type};base64,{encoded}"
        return {
            "role": message.role,
            "content": [
                {"type": "text", "text": message.content},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
