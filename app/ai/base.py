"""Interfaz abstracta del servicio de IA."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .types import AIMessage, AIResult


class AIService(ABC):
    """Frontera limpia para generación de texto y visión.

    El resto de la aplicación depende únicamente de esta interfaz, nunca del
    SDK de un proveedor concreto.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[AIMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIResult:
        """Genera una respuesta a partir de ``messages`` (texto y/o imagen)."""
