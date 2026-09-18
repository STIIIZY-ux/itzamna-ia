"""Servicio de materias."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Subject
from app.db.session import session_scope
from app.domain.errors import DuplicateError, NotFoundError
from app.repositories.subjects import SubjectRepository


class SubjectService:
    """Casos de uso sobre materias académicas."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_subject(self, *, user_id: int, name: str) -> Subject:
        try:
            async with session_scope(self._session_factory) as session:
                repo = SubjectRepository(session)
                return await repo.create(user_id=user_id, name=name)
        except IntegrityError as exc:
            raise DuplicateError(f"La materia '{name}' ya existe") from exc

    async def list_subjects(self, *, user_id: int) -> list[Subject]:
        async with session_scope(self._session_factory) as session:
            repo = SubjectRepository(session)
            return await repo.list_subjects(user_id=user_id)

    async def get_subject(self, *, user_id: int, subject_id: int) -> Subject:
        async with session_scope(self._session_factory) as session:
            repo = SubjectRepository(session)
            subject = await repo.get(user_id=user_id, subject_id=subject_id)
            if subject is None:
                raise NotFoundError(f"Materia {subject_id} no encontrada")
            return subject

    async def delete_subject(self, *, user_id: int, subject_id: int) -> bool:
        async with session_scope(self._session_factory) as session:
            repo = SubjectRepository(session)
            return await repo.delete(user_id=user_id, subject_id=subject_id)
