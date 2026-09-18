"""Tests de aislamiento entre usuarios (seguridad crítica)."""

import pytest

from app.domain.enums import TaskStatus
from app.domain.errors import DuplicateError, NotFoundError


async def _two_users(user_service):
    a = await user_service.get_or_create_by_telegram(telegram_id=301)
    b = await user_service.get_or_create_by_telegram(telegram_id=302)
    return a.id, b.id


async def test_user_b_cannot_read_user_a_task(session, user_service, task_service) -> None:
    a_id, b_id = await _two_users(user_service)
    task = await task_service.create_task(user_id=a_id, title="Privada")

    with pytest.raises(NotFoundError):
        await task_service.get_task(user_id=b_id, task_id=task.id)


async def test_user_b_list_does_not_include_user_a_tasks(
    session, user_service, task_service
) -> None:
    a_id, b_id = await _two_users(user_service)
    await task_service.create_task(user_id=a_id, title="De A")
    await task_service.create_task(user_id=b_id, title="De B")

    listed = await task_service.list_tasks(user_id=b_id)
    assert [t.title for t in listed] == ["De B"]


async def test_user_b_cannot_update_or_delete_user_a_task(
    session, user_service, task_service
) -> None:
    a_id, b_id = await _two_users(user_service)
    task = await task_service.create_task(user_id=a_id, title="De A")

    with pytest.raises(NotFoundError):
        await task_service.update_task(user_id=b_id, task_id=task.id, title="Hack")
    assert await task_service.delete_task(user_id=b_id, task_id=task.id) is False
    assert (await task_service.get_task(user_id=a_id, task_id=task.id)).title == "De A"


async def test_user_b_cannot_list_user_a_subjects(session, user_service, subject_service) -> None:
    a_id, b_id = await _two_users(user_service)
    await subject_service.create_subject(user_id=a_id, name="Materia de A")

    assert await subject_service.list_subjects(user_id=b_id) == []


async def test_same_subject_name_allowed_for_different_users(
    session, user_service, subject_service
) -> None:
    a_id, b_id = await _two_users(user_service)
    await subject_service.create_subject(user_id=a_id, name="Cálculo")
    await subject_service.create_subject(user_id=b_id, name="Cálculo")  # no debe fallar


async def test_duplicate_subject_same_user_raises(session, user_service, subject_service) -> None:
    a_id, _ = await _two_users(user_service)
    await subject_service.create_subject(user_id=a_id, name="Física")
    with pytest.raises(DuplicateError):
        await subject_service.create_subject(user_id=a_id, name="Física")


async def test_manipulating_task_id_cannot_cross_users(session, user_service, task_service) -> None:
    """Aunque se conozca el ID de una tarea ajena, no se puede acceder."""
    a_id, b_id = await _two_users(user_service)
    task = await task_service.create_task(user_id=a_id, title="Secreto de A")

    # Intento de cambiar estado usando el ID de la tarea de A desde B.
    with pytest.raises(NotFoundError):
        await task_service.change_status(
            user_id=b_id, task_id=task.id, new_status=TaskStatus.TERMINADA
        )
