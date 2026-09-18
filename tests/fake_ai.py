"""AIService simulado para tests."""

from __future__ import annotations

from app.ai.base import AIService
from app.ai.types import AIMessage, AIResult


class FakeAIService(AIService):
    """Devuelve respuestas en orden; registra las llamadas."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls: list[list[AIMessage]] = []

    async def complete(
        self,
        messages: list[AIMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIResult:
        self.calls.append(messages)
        if self._responses:
            content = self._responses.pop(0)
        else:
            content = "respuesta por defecto"
        return AIResult(content=content, provider="fake", model="fake-model")
