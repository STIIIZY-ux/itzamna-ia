"""Deduplicación de eventos de Google Calendar.

Los eventos duplicados pueden tener ``source_event_id`` distintos, por lo que
la unicidad ``(source, source_event_id)`` no basta. Aquí se calcula una
"huella" de alto nivel que se usa como segunda capa de detección.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_WHITESPACE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Normaliza un título para comparación (minúsculas, espacios colapsados)."""
    return _WHITESPACE.sub(" ", (title or "").strip().lower())


def date_key(due_at: datetime | None, timezone: str | None) -> str | None:
    """Devuelve la fecha de entrega (YYYY-MM-DD) en la zona horaria del evento."""
    if due_at is None:
        return None
    zone: ZoneInfo | None = None
    if timezone:
        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            zone = None
    if zone is not None:
        return due_at.astimezone(zone).date().isoformat()
    return due_at.date().isoformat()


def fingerprint(
    *, title: str, due_at: datetime | None, timezone: str | None, subject: str | None
) -> tuple[str, str | None, str | None]:
    """Huella (título normalizado, fecha, materia) de un evento."""
    return (
        normalize_title(title),
        date_key(due_at, timezone),
        normalize_title(subject) if subject else None,
    )


def are_high_confidence_duplicates(
    fp1: tuple[str, str | None, str | None], fp2: tuple[str, str | None, str | None]
) -> bool:
    """Dos huellas idénticas indican alta probabilidad de duplicado."""
    return fp1 == fp2
