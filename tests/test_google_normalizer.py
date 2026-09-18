"""Tests de normalización de eventos de Google Calendar."""

from datetime import datetime

from app.integrations.google.normalizer import normalize_event

TZ = "America/Tijuana"


def test_timed_event_preserves_instant() -> None:
    raw = {
        "id": "evt1",
        "summary": "Entrega 1",
        "description": "Resolver problemas",
        "start": {"dateTime": "2026-09-04T23:59:00-07:00", "timeZone": TZ},
    }
    event = normalize_event(raw, TZ)
    assert event.event_id == "evt1"
    assert event.title == "Entrega 1"
    assert event.due_at == datetime.fromisoformat("2026-09-04T23:59:00-07:00")
    assert event.timezone == TZ
    assert event.description == "Resolver problemas"


def test_all_day_event() -> None:
    raw = {"id": "evt2", "summary": "Entrega ensayo", "start": {"date": "2026-09-04"}}
    event = normalize_event(raw, TZ)
    assert event.due_at is not None
    assert event.due_at.date().isoformat() == "2026-09-04"
    assert event.timezone == TZ


def test_missing_start() -> None:
    raw = {"id": "evt3", "summary": "Sin fecha"}
    event = normalize_event(raw, TZ)
    assert event.due_at is None
    assert event.title == "Sin fecha"


def test_subject_from_title_bracket() -> None:
    raw = {
        "id": "evt4",
        "summary": "[Cálculo] Entrega 2",
        "start": {"dateTime": "2026-09-05T12:00:00-07:00"},
    }
    event = normalize_event(raw, TZ)
    assert event.subject == "Cálculo"


def test_subject_from_description() -> None:
    raw = {
        "id": "evt5",
        "summary": "Tarea",
        "description": "Materia: Programación\nHacer práctica",
        "start": {"date": "2026-09-06"},
    }
    event = normalize_event(raw, TZ)
    assert event.subject == "Programación"


def test_resources_extracted() -> None:
    raw = {
        "id": "evt6",
        "summary": "Tarea con pdf",
        "description": "ver https://example.com/doc.pdf y https://example.com/guia",
    }
    event = normalize_event(raw, TZ)
    uris = {r.uri for r in event.resources}
    assert "https://example.com/doc.pdf" in uris
    assert "https://example.com/guia" in uris
    types = {r.resource_type for r in event.resources}
    assert "pdf" in types
    assert "enlace" in types


def test_attachments_extracted() -> None:
    raw = {
        "id": "evt7",
        "summary": "Tarea con adjunto",
        "attachments": [
            {"fileUrl": "https://drive.google.com/file/x", "title": "guia", "mimeType": "application/pdf"}
        ],
    }
    event = normalize_event(raw, TZ)
    assert any(r.resource_type == "pdf" for r in event.resources)
