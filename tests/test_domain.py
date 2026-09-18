"""Tests del dominio: enums y máquina de estados."""

import pytest

from app.domain.enums import (
    CommitmentStatus,
    HistoryEventType,
    ResourceType,
    TaskPriority,
    TaskSource,
    TaskStatus,
)
from app.domain.state_machine import ALLOWED_TRANSITIONS, can_transition


def test_task_status_values() -> None:
    assert {s.value for s in TaskStatus} == {
        "pendiente",
        "notificada",
        "compromiso",
        "iniciada",
        "en_progreso",
        "terminada",
        "entregada",
        "bloqueada",
    }


def test_priority_values() -> None:
    assert {p.value for p in TaskPriority} == {"baja", "media", "alta", "urgente"}


def test_source_values() -> None:
    assert {s.value for s in TaskSource} == {"manual", "google_calendar"}


def test_commitment_status_values() -> None:
    assert {s.value for s in CommitmentStatus} == {"activo", "completado", "cancelado"}


def test_history_event_type_values() -> None:
    assert HistoryEventType.CREADA.value == "creada"
    assert HistoryEventType.ESTADO_CAMBIADO.value == "estado_cambiado"


def test_resource_type_values() -> None:
    assert ResourceType.PDF.value == "pdf"
    assert ResourceType.EVIDENCIA.value == "evidencia"


@pytest.mark.parametrize(
    "source,target",
    [
        (TaskStatus.PENDIENTE, TaskStatus.NOTIFICADA),
        (TaskStatus.PENDIENTE, TaskStatus.COMPROMISO),
        (TaskStatus.PENDIENTE, TaskStatus.INICIADA),
        (TaskStatus.INICIADA, TaskStatus.EN_PROGRESO),
        (TaskStatus.EN_PROGRESO, TaskStatus.TERMINADA),
        (TaskStatus.TERMINADA, TaskStatus.ENTREGADA),
        (TaskStatus.BLOQUEADA, TaskStatus.PENDIENTE),
    ],
)
def test_valid_transitions(source: TaskStatus, target: TaskStatus) -> None:
    assert can_transition(source, target) is True


@pytest.mark.parametrize(
    "source,target",
    [
        (TaskStatus.PENDIENTE, TaskStatus.ENTREGADA),
        (TaskStatus.PENDIENTE, TaskStatus.EN_PROGRESO),
        (TaskStatus.ENTREGADA, TaskStatus.PENDIENTE),
        (TaskStatus.TERMINADA, TaskStatus.PENDIENTE),
        (TaskStatus.COMPROMISO, TaskStatus.ENTREGADA),
    ],
)
def test_invalid_transitions(source: TaskStatus, target: TaskStatus) -> None:
    assert can_transition(source, target) is False


def test_entregada_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[TaskStatus.ENTREGADA] == frozenset()
