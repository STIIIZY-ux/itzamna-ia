"""Tests del servicio de compromisos."""

import pytest

from app.domain.enums import CommitmentStatus
from app.domain.errors import NotFoundError


async def _user_and_task(user_service, task_service, telegram_id: int):
    user = await user_service.get_or_create_by_telegram(telegram_id=telegram_id)
    task = await task_service.create_task(user_id=user.id, title="Tarea")
    return user.id, task.id


async def test_create_and_list_commitments(session, user_service, task_service, commitment_service) -> None:
    user_id, task_id = await _user_and_task(user_service, task_service, 200)

    commitment = await commitment_service.create_commitment(user_id=user_id, task_id=task_id, note="Ahora")
    assert commitment.status is CommitmentStatus.ACTIVO

    listed = await commitment_service.list_commitments(user_id=user_id, task_id=task_id)
    assert len(listed) == 1


async def test_create_commitment_foreign_task_raises(
    session, user_service, task_service, commitment_service
) -> None:
    _user_a_id, task_a_id = await _user_and_task(user_service, task_service, 201)
    user_b = await user_service.get_or_create_by_telegram(telegram_id=202)

    with pytest.raises(NotFoundError):
        await commitment_service.create_commitment(user_id=user_b.id, task_id=task_a_id)


async def test_complete_commitment(session, user_service, task_service, commitment_service) -> None:
    user_id, task_id = await _user_and_task(user_service, task_service, 203)
    commitment = await commitment_service.create_commitment(user_id=user_id, task_id=task_id)

    completed = await commitment_service.complete_commitment(
        user_id=user_id, commitment_id=commitment.id
    )
    assert completed.status is CommitmentStatus.COMPLETADO
    assert completed.completed_at is not None


async def test_cancel_commitment(session, user_service, task_service, commitment_service) -> None:
    user_id, task_id = await _user_and_task(user_service, task_service, 204)
    commitment = await commitment_service.create_commitment(user_id=user_id, task_id=task_id)

    cancelled = await commitment_service.cancel_commitment(
        user_id=user_id, commitment_id=commitment.id
    )
    assert cancelled.status is CommitmentStatus.CANCELADO


async def test_complete_foreign_commitment_raises(
    session, user_service, task_service, commitment_service
) -> None:
    user_a_id, task_a_id = await _user_and_task(user_service, task_service, 205)
    commitment = await commitment_service.create_commitment(user_id=user_a_id, task_id=task_a_id)

    user_b = await user_service.get_or_create_by_telegram(telegram_id=206)
    with pytest.raises(NotFoundError):
        await commitment_service.complete_commitment(
            user_id=user_b.id, commitment_id=commitment.id
        )
