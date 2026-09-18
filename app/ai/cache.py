"""Caché de resultados de IA (TTL en memoria) y decorador."""

from __future__ import annotations

import hashlib
import json
import logging
import time

from app.ai.base import AIService
from app.ai.types import AIMessage, AIResult

logger = logging.getLogger(__name__)


def cache_key(messages: list[AIMessage], *, max_tokens: int | None, temperature: float | None) -> str:
    """Clave determinista que incluye el contenido del mensaje y parámetros."""
    payload = {
        "messages": [
            {"role": m.role, "content": m.content, "has_image": m.image is not None}
            for m in messages
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AICache:
    """Caché TTL simple en memoria."""

    def __init__(self, ttl_seconds: float = 3600.0, max_entries: int = 512) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._store: dict[str, tuple[float, AIResult]] = {}

    def get(self, key: str) -> AIResult | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, result = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return result

    def set(self, key: str, result: AIResult) -> None:
        if len(self._store) >= self._max_entries:
            # evicta una entrada arbitraria (simple)
            oldest = next(iter(self._store))
            self._store.pop(oldest, None)
        self._store[key] = (time.monotonic() + self._ttl, result)


class CachedAIService(AIService):
    """Envuelve un ``AIService`` con caché; los hits no cuentan contra el rate limit."""

    def __init__(self, inner: AIService, cache: AICache) -> None:
        self._inner = inner
        self._cache = cache

    async def complete(
        self,
        messages: list[AIMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIResult:
        key = cache_key(messages, max_tokens=max_tokens, temperature=temperature)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = await self._inner.complete(
            messages, max_tokens=max_tokens, temperature=temperature
        )
        self._cache.set(key, result)
        return result
