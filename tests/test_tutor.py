"""Tests del tutor académico."""

import pytest

from app.ai.errors import AIConfigError
from app.services.tutor import TutorService
from tests.fake_ai import FakeAIService

_CONTEXT = {
    "title": "Estructuras secuenciales",
    "subject": "Programación",
    "instructions": "Hacer los ejercicios 1-5",
    "description": None,
    "resources": [],
    "due": "mañana",
}


async def test_generate_concepto() -> None:
    ai = FakeAIService(["💡 Concepto: ..."])
    content = await TutorService(ai).generate(kind="concepto", **_CONTEXT)
    assert "Concepto" in content


async def test_generate_all_kinds() -> None:
    ai = FakeAIService()
    for kind in ("concepto", "tip", "dato", "explica", "pregunta", "recomienda"):
        content = await TutorService(ai).generate(kind=kind, **_CONTEXT)
        assert isinstance(content, str)


async def test_generate_invalid_kind() -> None:
    with pytest.raises(ValueError):
        await TutorService(FakeAIService()).generate(kind="no_existe", **_CONTEXT)


async def test_generate_without_ai_raises() -> None:
    with pytest.raises(AIConfigError):
        await TutorService(None).generate(kind="concepto", **_CONTEXT)


async def test_generate_sends_context_to_model() -> None:
    ai = FakeAIService(["ok"])
    await TutorService(ai).generate(kind="tip", **_CONTEXT)
    assert len(ai.calls) == 1
    user_content = ai.calls[0][1].content
    assert "Estructuras secuenciales" in user_content
    assert "Programación" in user_content
