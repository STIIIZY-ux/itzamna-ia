"""Rate limiter de IA (ventana deslizante) y decorador de AIService."""

from __future__ import annotations

import logging
import time
from collections import deque

from app.ai.base import AIService
from app.ai.errors import AIRateLimitError
from app.ai.types import AIMessage, AIResult

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Ventana deslizante en memoria (por instancia).

    Para un despliegue de una única instancia (usuario único, costo $0) es
    suficiente; un limiter distribuido (Redis/DB) sería necesario en
    multi-instancia con límites globales estrictos.
    """

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        self._max_calls = max_calls
        self._window = window_seconds
        self._timestamps: deque[float] = deque()

    def acquire(self) -> bool:
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] >= self._window:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._max_calls:
            return False
        self._timestamps.append(now)
        return True

    @property
    def remaining(self) -> int:
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] >= self._window:
            self._timestamps.popleft()
        return max(0, self._max_calls - len(self._timestamps))


class RateLimitedAIService(AIService):
    """Envuelve un ``AIService`` aplicando el límite de llamadas por hora."""

    def __init__(self, inner: AIService, limiter: SlidingWindowRateLimiter) -> None:
        self._inner = inner
        self._limiter = limiter

    async def complete(
        self,
        messages: list[AIMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIResult:
        if not self._limiter.acquire():
            logger.warning("Llamada a IA rechazada por límite (restantes: %s)", self._limiter.remaining)
            raise AIRateLimitError("Límite de llamadas a IA alcanzado")
        try:
            result = await self._inner.complete(
                messages, max_tokens=max_tokens, temperature=temperature
            )
        except AIRateLimitError:
            raise
        except Exception as exc:
            logger.error("Error en llamada a IA: %s", exc)
            raise
        logger.debug(
            "Llamada a IA completada (modelo=%s, tokens=%s, restantes=%s)",
            result.model,
            result.usage.total_tokens if result.usage else "?",
            self._limiter.remaining,
        )
        return result
