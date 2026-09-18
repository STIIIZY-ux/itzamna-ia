"""Construcción del servicio de IA desde la configuración."""

from __future__ import annotations

from app.config import Settings

from .base import AIService
from .cache import AICache, CachedAIService
from .client import OpenAICompatibleAIService
from .rate_limit import RateLimitedAIService, SlidingWindowRateLimiter


def build_ai_service(settings: Settings) -> AIService | None:
    """Devuelve un ``AIService`` o ``None`` si la IA está deshabilitada.

    La clave se resuelve como ``AI_API_KEY`` o ``GEMINI_API_KEY``; el modelo
    como ``GEMINI_MODEL`` o ``AI_MODEL``. Si ``AI_ENABLED=false`` o no hay
    clave, la IA queda desactivada y el resto degrada de forma determinista.

    El servicio resultante se envuelve con rate limiter y caché: los hits de
    caché no cuentan contra el límite de llamadas.
    """
    if not settings.ai_enabled:
        return None
    api_key = settings.ai_api_key or settings.gemini_api_key
    if not api_key:
        return None

    base: AIService = OpenAICompatibleAIService(
        api_key=api_key,
        model=settings.gemini_model or settings.ai_model,
        base_url=settings.ai_base_url,
        timeout_seconds=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
        max_tokens=settings.ai_max_tokens,
    )
    limiter = SlidingWindowRateLimiter(
        max_calls=settings.ai_max_calls_per_hour, window_seconds=3600.0
    )
    limited: AIService = RateLimitedAIService(base, limiter)
    if settings.ai_cache_ttl_seconds > 0:
        return CachedAIService(limited, AICache(ttl_seconds=settings.ai_cache_ttl_seconds))
    return limited
