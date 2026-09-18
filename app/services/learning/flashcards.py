"""Servicio de flashcards con repetición espaciada."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Flashcard
from app.db.session import session_scope
from app.domain.enums import FlashcardStatus
from app.repositories.learning import FlashcardRepository

from .spaced_repetition import next_review_at


class FlashcardService:
    """Gestión de flashcards y su programación de repaso."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        *,
        user_id: int,
        front: str,
        back: str,
        concept_id: int | None = None,
        source: str | None = None,
        difficulty: int = 2,
    ) -> Flashcard:
        async with session_scope(self._session_factory) as session:
            return await FlashcardRepository(session).create(
                user_id=user_id, front=front, back=back, concept_id=concept_id, source=source, difficulty=difficulty
            )

    async def review(
        self, *, user_id: int, card_id: int, correct: bool, now: datetime | None = None
    ) -> Flashcard:
        now = now or datetime.now(timezone.utc)
        async with session_scope(self._session_factory) as session:
            repo = FlashcardRepository(session)
            card = await repo.get(user_id=user_id, card_id=card_id)
            if card is None:
                raise LookupError(f"Flashcard {card_id} no encontrada")
            if card.status is FlashcardStatus.NEW:
                status = FlashcardStatus.LEARNING
            else:
                status = FlashcardStatus.REVIEW
            return await repo.update_review(
                card,
                status=status,
                last_reviewed_at=now,
                next_review_at=next_review_at(now, correct=correct, difficulty=card.difficulty),
            )

    async def list_due(self, *, user_id: int, now: datetime | None = None, limit: int = 10) -> list[Flashcard]:
        now = now or datetime.now(timezone.utc)
        async with session_scope(self._session_factory) as session:
            return await FlashcardRepository(session).list_due(user_id=user_id, now=now, limit=limit)

    async def list_new(self, *, user_id: int, limit: int = 10) -> list[Flashcard]:
        async with session_scope(self._session_factory) as session:
            return await FlashcardRepository(session).list_new(user_id=user_id, limit=limit)
