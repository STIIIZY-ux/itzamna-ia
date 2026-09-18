"""Repositorio de materias."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subject


class SubjectRepository:
    """Acceso a datos de :class:`Subject`, siempre acotado por usuario."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: int, name: str) -> Subject:
        subject = Subject(user_id=user_id, name=name)
        self._session.add(subject)
        await self._session.flush()
        return subject

    async def get(self, *, user_id: int, subject_id: int) -> Subject | None:
        result = await self._session.execute(
            select(Subject).where(Subject.id == subject_id, Subject.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, *, user_id: int, name: str) -> Subject | None:
        result = await self._session.execute(
            select(Subject).where(Subject.user_id == user_id, Subject.name == name)
        )
        return result.scalar_one_or_none()

    async def get_by_name_ci(self, *, user_id: int, name: str) -> Subject | None:
        result = await self._session.execute(
            select(Subject).where(
                Subject.user_id == user_id, func.lower(Subject.name) == name.lower()
            )
        )
        return result.scalar_one_or_none()

    async def list_subjects(self, *, user_id: int) -> list[Subject]:
        result = await self._session.execute(
            select(Subject).where(Subject.user_id == user_id).order_by(Subject.name)
        )
        return list(result.scalars().all())

    async def delete(self, *, user_id: int, subject_id: int) -> bool:
        subject = await self.get(user_id=user_id, subject_id=subject_id)
        if subject is None:
            return False
        await self._session.delete(subject)
        await self._session.flush()
        return True
