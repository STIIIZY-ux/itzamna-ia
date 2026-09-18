"""Servicio de conceptos y dominio."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Concept
from app.db.session import session_scope
from app.repositories.learning import ConceptRepository

from .mastery import update_mastery
from .spaced_repetition import next_review_at

DEFAULT_WEAK_THRESHOLD = 0.6


class ConceptService:
    """Gestión de conceptos y su métrica de dominio."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_or_create(
        self,
        *,
        user_id: int,
        name: str,
        description: str | None = None,
        subject_id: int | None = None,
        source: str | None = None,
        source_ref: str | None = None,
    ) -> Concept:
        async with session_scope(self._session_factory) as session:
            repo = ConceptRepository(session)
            existing = await repo.get_by_name(user_id=user_id, name=name)
            if existing is not None:
                return existing
            try:
                return await repo.create(
                    user_id=user_id,
                    name=name,
                    description=description,
                    subject_id=subject_id,
                    source=source,
                    source_ref=source_ref,
                )
            except IntegrityError:
                await session.rollback()
                existing = await repo.get_by_name(user_id=user_id, name=name)
                if existing is None:
                    raise
                return existing

    async def record_answer(
        self,
        *,
        user_id: int,
        concept_id: int,
        correct: bool,
        difficulty: int = 2,
        now: datetime | None = None,
    ) -> Concept:
        now = now or datetime.now(timezone.utc)
        async with session_scope(self._session_factory) as session:
            repo = ConceptRepository(session)
            concept = await repo.get(user_id=user_id, concept_id=concept_id)
            if concept is None:
                raise LookupError(f"Concepto {concept_id} no encontrado")
            new_mastery = update_mastery(concept.mastery, correct=correct, difficulty=difficulty)
            return await repo.update_mastery(
                concept,
                mastery=new_mastery,
                last_reviewed_at=now,
                next_review_at=next_review_at(
                    now, correct=correct, difficulty=difficulty, mastery=new_mastery
                ),
            )

    async def list_weak(self, *, user_id: int, threshold: float = DEFAULT_WEAK_THRESHOLD) -> list[Concept]:
        async with session_scope(self._session_factory) as session:
            return await ConceptRepository(session).list_weak(user_id=user_id, threshold=threshold)

    async def list_due(self, *, user_id: int, now: datetime | None = None) -> list[Concept]:
        now = now or datetime.now(timezone.utc)
        async with session_scope(self._session_factory) as session:
            return await ConceptRepository(session).list_due(user_id=user_id, now=now)
