"""Servicio de repaso (/repaso): prioriza débiles, atrasados, importantes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import session_scope
from app.repositories.learning import ConceptRepository, FlashcardRepository

WEAK_THRESHOLD = 0.6


@dataclass(frozen=True)
class ReviewItem:
    kind: str  # "flashcard" | "concept"
    id: int
    front: str
    back: str


class ReviewService:
    """Selecciona qué repasar: flashcards atrasadas y conceptos débiles/atrasados."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def pick(self, *, user_id: int, now: datetime | None = None, limit: int = 10) -> list[ReviewItem]:
        now = now or datetime.now(timezone.utc)
        async with session_scope(self._session_factory) as session:
            cards = await FlashcardRepository(session).list_due(user_id=user_id, now=now, limit=limit)
            weak = await ConceptRepository(session).list_weak(user_id=user_id, threshold=WEAK_THRESHOLD)
            due_concepts = await ConceptRepository(session).list_due(user_id=user_id, now=now)

        items: list[ReviewItem] = []
        for card in cards:
            items.append(ReviewItem(kind="flashcard", id=card.id, front=card.front, back=card.back))

        seen: set[str] = set()
        for concept in due_concepts + weak:
            key = f"concept:{concept.id}"
            if key in seen:
                continue
            seen.add(key)
            items.append(
                ReviewItem(
                    kind="concept",
                    id=concept.id,
                    front=concept.name,
                    back=concept.description or "(sin descripción)",
                )
            )

        return items[:limit]
