"""Representación interna normalizada de un evento de Google Calendar."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedResource(BaseModel):
    """Referencia a un recurso/enlace de un evento (sin descarga)."""

    resource_type: str  # 'pdf' | 'enlace' | 'otro'
    name: str | None = None
    uri: str | None = None


class NormalizedEvent(BaseModel):
    """Evento de Google Calendar normalizado, independiente de la tarea interna.

    Los campos ausentes en el evento original quedan como ``None``. ``raw``
    conserva el dict original para auditoría.
    """

    event_id: str
    title: str
    subject: str | None = None
    description: str | None = None
    instructions: str | None = None
    due_at: datetime | None = None
    timezone: str | None = None
    resources: list[NormalizedResource] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
