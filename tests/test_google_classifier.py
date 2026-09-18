"""Tests de la clasificación heurística de eventos."""

import pytest

from app.integrations.google.classifier import is_task_event


@pytest.mark.parametrize(
    "summary,expected",
    [
        ("Entrega 3", True),
        ("Examen de cálculo", True),
        ("Control de lectura capítulo 5", True),
        ("Tarea de programación", True),
        ("Actividad 3", True),
        ("Proyecto final", True),
        ("Quiz de historia", True),
        ("Clase de cálculo", False),
        ("Reunión de equipo", False),
        ("Cumpleaños de Juan", False),
        ("Gimnasio", False),
        ("Evento personal", False),
        ("", False),
        (None, False),
    ],
)
def test_is_task_event(summary, expected) -> None:
    assert is_task_event(summary) is expected
