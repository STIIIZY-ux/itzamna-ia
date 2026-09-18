"""Tests del servicio de tareas (núcleo de negocio)."""

import pytest

from app.domain.enums import HistoryEventType, TaskPriority, TaskSource, TaskStatus
from app.domain.errors import InvalidStateTransitionError, NotFoundError


async def _make_user(user_service, telegram_id: int) -> int:
    user = await user_service.get_or_create_by_telegram(
        telegram_id=telegram_id, first_name="Test"
    )
    return user.id


async def test_create_task_logs_creation_history(session, task_service, user_service) -> None:
    user_id = await _make_user(user_service, 111)
    task = await task_service.create_task(user_id=user_id, title="Estudiar capítulo 2")
    assert task.status is TaskStatus.PENDIENTE
    assert task.source is TaskSource.MANUAL
    assert task.priority is TaskPriority.MEDIA

    fetched = await task_service.get_task(user_id=user_id, task_id=task.id)
    assert fetched.title == "Estudiar capítulo 2"
    assert [h.event_type for h in fetched.history] == [HistoryEventType.CREADA]


async def test_create_task_with_subject(session, task_service, user_service, subject_service) -> None:
    user_id = await _make_user(user_service, 112)
    subject = await subject_service.create_subject(user_id=user_id, name="Programación")
    task = await task_service.create_task(
        user_id=user_id, title="Entregar práctica", subject_id=subject.id
    )
    assert task.subject_id == subject.id


async def test_create_task_with_foreign_subject_raises(
    session, task_service, user_service, subject_service
) -> None:
    user_a = await _make_user(user_service, 113)
    user_b = await _make_user(user_service, 114)
    subject_b = await subject_service.create_subject(user_id=user_b, name="Química")

    with pytest.raises(NotFoundError):
        await task_service.create_task(user_id=user_a, title="T", subject_id=subject_b.id)


async def test_change_status_valid_transition(session, task_service, user_service) -> None:
    user_id = await _make_user(user_service, 115)
    task = await task_service.create_task(user_id=user_id, title="T")

    updated = await task_service.change_status(
        user_id=user_id, task_id=task.id, new_status=TaskStatus.INICIADA
    )
    assert updated.status is TaskStatus.INICIADA

    fetched = await task_service.get_task(user_id=user_id, task_id=task.id)
    history_types = [h.event_type for h in fetched.history]
    assert history_types == [HistoryEventType.CREADA, HistoryEventType.ESTADO_CAMBIADO]
    estado = next(h for h in fetched.history if h.event_type is HistoryEventType.ESTADO_CAMBIADO)
    assert estado.from_value == "pendiente"
    assert estado.to_value == "iniciada"


async def test_change_status_invalid_transition_raises(session, task_service, user_service) -> None:
    user_id = await _make_user(user_service, 116)
    task = await task_service.create_task(user_id=user_id, title="T")

    with pytest.raises(InvalidStateTransitionError):
        await task_service.change_status(
            user_id=user_id, task_id=task.id, new_status=TaskStatus.ENTREGADA
        )


async def test_update_task_priority_logs_history(session, task_service, user_service) -> None:
    user_id = await _make_user(user_service, 117)
    task = await task_service.create_task(user_id=user_id, title="T")

    updated = await task_service.update_task(
        user_id=user_id, task_id=task.id, priority=TaskPriority.URGENTE
    )
    assert updated.priority is TaskPriority.URGENTE

    fetched = await task_service.get_task(user_id=user_id, task_id=task.id)
    assert HistoryEventType.PRIORIDAD_CAMBIADA in [h.event_type for h in fetched.history]


async def test_update_task_unknown_field_raises(session, task_service, user_service) -> None:
    user_id = await _make_user(user_service, 118)
    task = await task_service.create_task(user_id=user_id, title="T")

    with pytest.raises(ValueError):
        await task_service.update_task(user_id=user_id, task_id=task.id, no_existe=1)


async def test_delete_task(session, task_service, user_service) -> None:
    user_id = await _make_user(user_service, 119)
    task = await task_service.create_task(user_id=user_id, title="T")
    assert await task_service.delete_task(user_id=user_id, task_id=task.id) is True
    with pytest.raises(NotFoundError):
        await task_service.get_task(user_id=user_id, task_id=task.id)


async def test_list_tasks_filters(session, task_service, user_service) -> None:
    user_id = await _make_user(user_service, 120)
    t1 = await task_service.create_task(user_id=user_id, title="A")
    await task_service.create_task(user_id=user_id, title="B")
    await task_service.change_status(user_id=user_id, task_id=t1.id, new_status=TaskStatus.INICIADA)

    all_tasks = await task_service.list_tasks(user_id=user_id)
    assert len(all_tasks) == 2
    iniciadas = await task_service.list_tasks(user_id=user_id, status=TaskStatus.INICIADA)
    assert len(iniciadas) == 1


async def test_task_service_requires_user_isolation(session, task_service, user_service) -> None:
    user_a = await _make_user(user_service, 121)
    user_b = await _make_user(user_service, 122)
    task = await task_service.create_task(user_id=user_a, title="Secreto")

    with pytest.raises(NotFoundError):
        await task_service.get_task(user_id=user_b, task_id=task.id)
    with pytest.raises(NotFoundError):
        await task_service.change_status(user_id=user_b, task_id=task.id, new_status=TaskStatus.INICIADA)
    assert await task_service.delete_task(user_id=user_b, task_id=task.id) is False
