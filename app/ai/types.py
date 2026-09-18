"""Tipos de la capa de IA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AIImage:
    """Imagen adjunta a un mensaje (para visión)."""

    data: bytes
    content_type: str


@dataclass(frozen=True)
class AIMessage:
    """Mensaje del historial de una conversación con el modelo."""

    role: str
    content: str
    image: AIImage | None = None


@dataclass(frozen=True)
class AIUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AIResult:
    """Resultado estructurado de una llamada al modelo."""

    content: str
    provider: str
    model: str
    usage: AIUsage | None = None
    latency_ms: float | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
