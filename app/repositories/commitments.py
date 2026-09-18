"""Repositorio de compromisos."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Commitment
from app.domain.enums import CommitmentStatus


class CommitmentRepository:
    """Acceso a datos de :class:`Commitment`, acotado por usuario."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        task_id: int,
        user_id: int,
        status: CommitmentStatus = CommitmentStatus.ACTIVO,
        note: str | None = None,
    ) -> Commitment:
        commitment = Commitment(task_id=task_id, user_id=user_id, status=status, note=note)
        self._session.add(commitment)
        await self._session.flush()
        return commitment

    async def get(self, *, user_id: int, commitment_id: int) -> Commitment | None:
        result = await self._session.execute(
            select(Commitment).where(
                Commitment.id == commitment_id, Commitment.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_task(self, *, user_id: int, task_id: int) -> list[Commitment]:
        result = await self._session.execute(
            select(Commitment)
            .where(Commitment.task_id == task_id, Commitment.user_id == user_id)
            .order_by(Commitment.committed_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_for_task(self, *, user_id: int, task_id: int) -> Commitment | None:
        result = await self._session.execute(
            select(Commitment)
            .where(
                Commitment.task_id == task_id,
                Commitment.user_id == user_id,
                Commitment.status == CommitmentStatus.ACTIVO,
            )
            .order_by(Commitment.committed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(self, *, user_id: int) -> list[Commitment]:
        result = await self._session.execute(
            select(Commitment)
            .where(Commitment.user_id == user_id, Commitment.status == CommitmentStatus.ACTIVO)
            .order_by(Commitment.committed_at.desc())
        )
        return list(result.scalars().all())

    async def count_by_status(self, *, user_id: int, status: CommitmentStatus) -> int:
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count(Commitment.id)).where(
                Commitment.user_id == user_id, Commitment.status == status
            )
        )
        return int(result.scalar_one())

    async def update_status(
        self,
        *,
        user_id: int,
        commitment_id: int,
        status: CommitmentStatus,
        completed_at: datetime | None = None,
    ) -> Commitment | None:
        commitment = await self.get(user_id=user_id, commitment_id=commitment_id)
        if commitment is None:
            return None
        commitment.status = status
        if status == CommitmentStatus.COMPLETADO:
            commitment.completed_at = completed_at or datetime.now().astimezone()
        await self._session.flush()
        return commitment
