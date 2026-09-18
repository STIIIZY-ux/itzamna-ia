"""Servicio de control de lectura (por capítulo, acumulativo y examen final)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.base import AIService
from app.db.models import Quiz
from app.db.session import session_scope
from app.domain.enums import ChapterStatus, QuizType
from app.repositories.learning import BookRepository, ChapterRepository
from app.services.learning.quizzes import QuizService

logger = logging.getLogger(__name__)

_CHAPTER_CONTROL_N = 5
_CUMULATIVE_N = 5
_FINAL_N = 10
_MAX_CONTEXT_CHARS = 30_000


class ReadingControlService:
    """Genera controles de lectura a partir del contenido real de los capítulos."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], ai: AIService | None
    ) -> None:
        self._session_factory = session_factory
        self._ai = ai

    async def chapter_control(
        self, *, user_id: int, book_id: int, chapter_id: int | None = None
    ) -> Quiz | None:
        async with session_scope(self._session_factory) as session:
            chapters = await ChapterRepository(session).list_for_book(book_id=book_id)
            book = await BookRepository(session).get(user_id=user_id, book_id=book_id)
        if book is None or not chapters:
            return None

        target = _pick_chapter(chapters, chapter_id)
        if target is None:
            return None

        quiz_service = QuizService(self._session_factory, self._ai)
        quiz = await quiz_service.generate_quiz(
            user_id=user_id,
            quiz_type=QuizType.CHAPTER,
            title=f"Control de lectura: {target.title}",
            context=target.content or "",
            n=_CHAPTER_CONTROL_N,
        )
        if quiz is not None:
            async with session_scope(self._session_factory) as session:
                chapter = await ChapterRepository(session).get(user_id=user_id, chapter_id=target.id)
                if chapter is not None:
                    await ChapterRepository(session).update(
                        chapter, status=ChapterStatus.CONTROL_PENDIENTE
                    )
        return quiz

    async def cumulative_control(self, *, user_id: int, book_id: int) -> Quiz | None:
        context = await self._cumulative_context(user_id=user_id, book_id=book_id)
        if not context:
            return None
        return await QuizService(self._session_factory, self._ai).generate_quiz(
            user_id=user_id,
            quiz_type=QuizType.CUMULATIVE,
            title="Repaso acumulativo",
            context=context,
            n=_CUMULATIVE_N,
        )

    async def final_exam(self, *, user_id: int, book_id: int) -> Quiz | None:
        context = await self._cumulative_context(user_id=user_id, book_id=book_id)
        if not context:
            return None
        return await QuizService(self._session_factory, self._ai).generate_quiz(
            user_id=user_id,
            quiz_type=QuizType.FINAL,
            title="Examen final",
            context=context,
            n=_FINAL_N,
        )

    async def _cumulative_context(self, *, user_id: int, book_id: int) -> str:
        async with session_scope(self._session_factory) as session:
            book = await BookRepository(session).get(user_id=user_id, book_id=book_id)
            chapters = await ChapterRepository(session).list_for_book(book_id=book_id)
        if book is None or not chapters:
            return ""
        parts: list[str] = []
        total = 0
        for chapter in chapters:
            if chapter.content is None:
                continue
            chunk = chapter.content[:_MAX_CONTEXT_CHARS // max(1, len(chapters))]
            parts.append(f"### {chapter.title}\n{chunk}")
            total += len(chunk)
            if total >= _MAX_CONTEXT_CHARS:
                break
        return "\n\n".join(parts)


def _pick_chapter(chapters, chapter_id: int | None):
    if chapter_id is not None:
        for chapter in chapters:
            if chapter.id == chapter_id:
                return chapter
        return None
    # Prefiere un capítulo pendiente de control o en lectura; si no, el primero.
    for status in (
        ChapterStatus.CONTROL_PENDIENTE,
        ChapterStatus.LEIDO,
        ChapterStatus.EN_LECTURA,
        ChapterStatus.PENDIENTE,
    ):
        for chapter in chapters:
            if chapter.status is status:
                return chapter
    return chapters[0] if chapters else None
