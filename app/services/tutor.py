"""Tutor académico basado en el contexto real de la actividad."""

from __future__ import annotations

from app.ai.base import AIService
from app.ai.errors import AIConfigError
from app.ai.prompts import TUTOR_SYSTEM_PROMPT, build_task_context
from app.ai.types import AIMessage

_KIND_INSTRUCTIONS = {
    "concepto": "Da un concepto express (1-2 frases) sobre el tema de la actividad.",
    "tip": "Da un tip práctico y breve para avanzar en esta actividad.",
    "dato": "Da un dato curioso relacionado con el tema de la actividad.",
    "explica": "Explica brevemente (máx. 5 líneas) el tema de la actividad.",
    "pregunta": "Haz una pregunta rápida de repaso sobre el tema.",
    "recomienda": "Recomienda el siguiente paso concreto para esta actividad.",
}

_VALID_KINDS = frozenset(_KIND_INSTRUCTIONS)


class TutorService:
    """Genera contenido académico breve a partir del contexto de una tarea."""

    def __init__(self, ai: AIService | None) -> None:
        self._ai = ai

    async def generate(
        self,
        *,
        kind: str,
        title: str,
        subject: str | None,
        instructions: str | None,
        description: str | None,
        resources: list[str] | None,
        due: str | None,
    ) -> str:
        if kind not in _VALID_KINDS:
            raise ValueError(f"kind de tutor no soportado: {kind}")
        if self._ai is None:
            raise AIConfigError("La IA no está disponible")

        instruction = _KIND_INSTRUCTIONS[kind]
        context = build_task_context(
            title=title,
            subject=subject,
            instructions=instructions,
            description=description,
            resources=resources,
            due=due,
        )
        messages = [
            AIMessage(role="system", content=TUTOR_SYSTEM_PROMPT),
            AIMessage(role="user", content=f"{instruction}\n\n{context}"),
        ]
        result = await self._ai.complete(messages, max_tokens=400)
        return result.content.strip()
