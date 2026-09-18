"""Tests del caché de IA."""

from app.ai.cache import AICache, CachedAIService, cache_key
from app.ai.types import AIMessage
from tests.fake_ai import FakeAIService


def test_cache_key_deterministic() -> None:
    a = cache_key([AIMessage(role="user", content="hola")], max_tokens=10, temperature=None)
    b = cache_key([AIMessage(role="user", content="hola")], max_tokens=10, temperature=None)
    c = cache_key([AIMessage(role="user", content="adios")], max_tokens=10, temperature=None)
    assert a == b
    assert a != c


async def test_cached_service_hits_cache() -> None:
    inner = FakeAIService(["respuesta"])
    service = CachedAIService(inner, AICache(ttl_seconds=60))

    r1 = await service.complete([AIMessage(role="user", content="x")])
    r2 = await service.complete([AIMessage(role="user", content="x")])

    assert r1.content == "respuesta"
    assert r2.content == "respuesta"
    assert len(inner.calls) == 1  # segunda llamada sirve de caché


def test_cache_ttl_expiry() -> None:
    cache = AICache(ttl_seconds=0)
    from app.ai.types import AIResult

    cache.set("k", AIResult(content="x", provider="p", model="m"))
    assert cache.get("k") is None
