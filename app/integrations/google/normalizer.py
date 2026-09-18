"""Normalización de eventos de Google Calendar a la representación interna."""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .resources import extract_resources
from .schemas import NormalizedEvent
from .subjects import extract_subject


def _safe_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _parse_rfc3339(value: str) -> datetime:
    # Python >= 3.11 `fromisoformat` soporta 'Z' y desplazamientos.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _extract_due(
    start: dict, default_timezone: str
) -> tuple[datetime | None, str | None]:
    """Devuelve ``(due_at, timezone)``.

    La fecha/hora del evento representa la FECHA/HORA DE ENTREGA (no el momento
    de comenzar). Para eventos con hora se conserva el instante exacto; para
    eventos de todo el día se usa la medianoche de esa fecha en la zona dada.
    """
    if "dateTime" in start:
        due_at = _parse_rfc3339(start["dateTime"])
        timezone = start.get("timeZone") or default_timezone
        return due_at, timezone

    if "date" in start:
        day = date.fromisoformat(start["date"])
        timezone = start.get("timeZone") or default_timezone
        zone = _safe_zone(timezone)
        return datetime(day.year, day.month, day.day, tzinfo=zone), timezone

    return None, None


def normalize_event(raw_event: dict, default_timezone: str) -> NormalizedEvent:
    """Convierte un evento crudo de Google en un :class:`NormalizedEvent`."""
    summary = (raw_event.get("summary") or "").strip()
    description = raw_event.get("description")
    start = raw_event.get("start") or {}

    due_at, timezone = _extract_due(start, default_timezone)

    return NormalizedEvent(
        event_id=raw_event.get("id") or "",
        title=summary or "(sin título)",
        subject=extract_subject(summary, description),
        description=description,
        instructions=None,
        due_at=due_at,
        timezone=timezone,
        resources=extract_resources(raw_event),
        raw=raw_event,
    )
