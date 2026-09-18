"""Servicio de compromisos (accountability)."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Commitment
from app.db.session import session_scope
from app.domain.enums import CommitmentStatus
from app.domain.errors import NotFoundError
from app.repositories.commitments import CommitmentRepository
from app.repositories.tasks import TaskRepository


class CommitmentService:
    """Casos de uso sobre compromisos del usuario."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_commitment(
        self, *, user_id: int, task_id: int, note: str | None = None
    ) -> Commitment:
        async with session_scope(self._session_factory) as session:
            task = await TaskRepository(session).get(user_id=user_id, task_id=task_id)
            if task is None:
                raise NotFoundError(f"Tarea {task_id} no encontrada")
            repo = CommitmentRepository(session)
            return await repo.create(task_id=task_id, user_id=user_id, note=note)

    async def list_commitments(self, *, user_id: int, task_id: int) -> list[Commitment]:
        async with session_scope(self._session_factory) as session:
            repo = CommitmentRepository(session)
            return await repo.list_for_task(user_id=user_id, task_id=task_id)

    async def complete_commitment(
        self, *, user_id: int, commitment_id: int
    ) -> Commitment:
        async with session_scope(self._session_factory) as session:
            repo = CommitmentRepository(session)
            commitment = await repo.update_status(
                user_id=user_id,
                commitment_id=commitment_id,
                status=CommitmentStatus.COMPLETADO,
                completed_at=datetime.now().astimezone(),
            )
            if commitment is None:
                raise NotFoundError(f"Compromiso {commitment_id} no encontrado")
            return commitment

    async def cancel_commitment(self, *, user_id: int, commitment_id: int) -> Commitment:
        async with session_scope(self._session_factory) as session:
            repo = CommitmentRepository(session)
            commitment = await repo.update_status(
                user_id=user_id, commitment_id=commitment_id, status=CommitmentStatus.CANCELADO
            )
            if commitment is None:
                raise NotFoundError(f"Compromiso {commitment_id} no encontrado")
            return commitment
