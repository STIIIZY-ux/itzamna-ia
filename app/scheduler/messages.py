"""Mensajes deterministas de recordatorios (sin IA)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.enums import JobKind


def format_due(due_at: datetime | None, timezone: str | None) -> str:
    if due_at is None:
        return "sin fecha"
    zone: ZoneInfo | None = None
    if timezone:
        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            zone = None
    dt = due_at.astimezone(zone) if zone else due_at
    return dt.strftime("%d %b %H:%M")


def build_reminder_message(kind: JobKind, task, *, timezone: str | None) -> str:
    """Construye un mensaje de recordatorio determinista."""
    title = task.title
    due = format_due(task.due_at, timezone or task.timezone)

    if kind is JobKind.START_REMINDER:
        return (
            f"⏰ Es hora de empezar: {title}\n"
            f"Entrega: {due}\n"
            "Revisa las instrucciones y comienza."
        )
    if kind is JobKind.DUE_REMINDER:
        return (
            f"⚠️ {title} vence pronto.\n"
            f"Entrega: {due}\n"
            "Si aún no has avanzado, empieza ahora."
        )
    if kind is JobKind.NUDGE:
        return f"👀 ¿Vas a avanzar con {title}?\nEntrega: {due}"
    if kind is JobKind.EVIDENCE_REQUEST:
        return f"📸 Envía evidencia de tu avance en {title}.\nEntrega: {due}"
    return f"Recordatorio: {title}"
