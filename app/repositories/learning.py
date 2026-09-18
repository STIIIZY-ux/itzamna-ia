"""Repositorios del Learning Engine (conceptos, preguntas, quizzes, flashcards, libros)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Book,
    Chapter,
    Concept,
    Flashcard,
    Question,
    Quiz,
    QuizAnswer,
    QuizQuestion,
)
from app.domain.enums import BookStatus, QuizStatus, QuizType


class ConceptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, user_id: int, concept_id: int) -> Concept | None:
        result = await self._session.execute(
            select(Concept).where(Concept.id == concept_id, Concept.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, *, user_id: int, name: str) -> Concept | None:
        result = await self._session.execute(
            select(Concept).where(
                Concept.user_id == user_id, func.lower(Concept.name) == name.lower()
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: int,
        name: str,
        description: str | None = None,
        subject_id: int | None = None,
        source: str | None = None,
        source_ref: str | None = None,
    ) -> Concept:
        concept = Concept(
            user_id=user_id,
            name=name,
            description=description,
            subject_id=subject_id,
            source=source,
            source_ref=source_ref,
        )
        self._session.add(concept)
        await self._session.flush()
        return concept

    async def list_weak(self, *, user_id: int, threshold: float) -> list[Concept]:
        result = await self._session.execute(
            select(Concept)
            .where(Concept.user_id == user_id, Concept.mastery < threshold)
            .order_by(Concept.mastery.asc())
        )
        return list(result.scalars().all())

    async def list_all(self, *, user_id: int) -> list[Concept]:
        result = await self._session.execute(
            select(Concept).where(Concept.user_id == user_id)
        )
        return list(result.scalars().all())

    async def average_mastery(self, *, user_id: int) -> float | None:
        result = await self._session.execute(
            select(func.avg(Concept.mastery)).where(Concept.user_id == user_id)
        )
        value = result.scalar_one()
        return float(value) if value is not None else None

    async def list_due(self, *, user_id: int, now: datetime) -> list[Concept]:
        result = await self._session.execute(
            select(Concept)
            .where(
                Concept.user_id == user_id,
                Concept.next_review_at.is_not(None),
                Concept.next_review_at <= now,
            )
            .order_by(Concept.next_review_at.asc())
        )
        return list(result.scalars().all())

    async def update_mastery(
        self, concept: Concept, *, mastery: float, last_reviewed_at: datetime, next_review_at: datetime | None
    ) -> Concept:
        concept.mastery = round(min(1.0, max(0.0, mastery)), 4)
        concept.last_reviewed_at = last_reviewed_at
        concept.next_review_at = next_review_at
        await self._session.flush()
        return concept


class QuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        question_type,
        prompt: str,
        concept_id: int | None = None,
        subject_id: int | None = None,
        book_id: int | None = None,
        chapter_id: int | None = None,
        expected_answer: str | None = None,
        explanation: str | None = None,
        options: list[str] | None = None,
        correct_index: int | None = None,
        difficulty: int = 2,
        source: str | None = None,
        source_ref: str | None = None,
    ) -> Question:
        question = Question(
            user_id=user_id,
            question_type=question_type,
            prompt=prompt,
            concept_id=concept_id,
            subject_id=subject_id,
            book_id=book_id,
            chapter_id=chapter_id,
            expected_answer=expected_answer,
            explanation=explanation,
            options=options,
            correct_index=correct_index,
            difficulty=difficulty,
            source=source,
            source_ref=source_ref,
        )
        self._session.add(question)
        await self._session.flush()
        return question

    async def get(self, *, user_id: int, question_id: int) -> Question | None:
        result = await self._session.execute(
            select(Question).where(Question.id == question_id, Question.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_chapter(self, *, user_id: int, chapter_id: int) -> list[Question]:
        result = await self._session.execute(
            select(Question).where(Question.user_id == user_id, Question.chapter_id == chapter_id)
        )
        return list(result.scalars().all())

    async def list_for_concept(self, *, user_id: int, concept_id: int) -> list[Question]:
        result = await self._session.execute(
            select(Question).where(Question.user_id == user_id, Question.concept_id == concept_id)
        )
        return list(result.scalars().all())


class QuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: int, quiz_type: QuizType, title: str) -> Quiz:
        quiz = Quiz(user_id=user_id, quiz_type=quiz_type, title=title)
        self._session.add(quiz)
        await self._session.flush()
        return quiz

    async def get(self, *, user_id: int, quiz_id: int) -> Quiz | None:
        result = await self._session.execute(
            select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active(self, *, user_id: int) -> Quiz | None:
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.user_id == user_id, Quiz.status == QuizStatus.IN_PROGRESS)
            .order_by(Quiz.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def add_question(self, *, quiz_id: int, question_id: int, order_index: int) -> QuizQuestion:
        link = QuizQuestion(quiz_id=quiz_id, question_id=question_id, order_index=order_index)
        self._session.add(link)
        await self._session.flush()
        return link

    async def list_questions(self, *, quiz_id: int) -> list[Question]:
        result = await self._session.execute(
            select(Question)
            .join(QuizQuestion, QuizQuestion.question_id == Question.id)
            .where(QuizQuestion.quiz_id == quiz_id)
            .order_by(QuizQuestion.order_index)
        )
        return list(result.scalars().all())

    async def update(self, quiz: Quiz, *, status: QuizStatus | None = None, score: float | None = None) -> Quiz:
        if status is not None:
            quiz.status = status
        if score is not None:
            quiz.score = score
        await self._session.flush()
        return quiz


class QuizAnswerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, user_id: int, quiz_id: int, question_id: int) -> QuizAnswer | None:
        result = await self._session.execute(
            select(QuizAnswer).where(
                QuizAnswer.user_id == user_id,
                QuizAnswer.quiz_id == quiz_id,
                QuizAnswer.question_id == question_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: int,
        quiz_id: int | None,
        question_id: int,
        user_answer: str,
        is_correct: bool | None = None,
        score: float | None = None,
        feedback: str | None = None,
        confidence: float | None = None,
    ) -> QuizAnswer:
        answer = QuizAnswer(
            user_id=user_id,
            quiz_id=quiz_id,
            question_id=question_id,
            user_answer=user_answer,
            is_correct=is_correct,
            score=score,
            feedback=feedback,
            confidence=confidence,
        )
        self._session.add(answer)
        await self._session.flush()
        return answer

    async def count_for_quiz(self, *, user_id: int, quiz_id: int) -> int:
        result = await self._session.execute(
            select(func.count(QuizAnswer.id)).where(
                QuizAnswer.user_id == user_id, QuizAnswer.quiz_id == quiz_id
            )
        )
        return int(result.scalar_one())

    async def count_for_user(self, *, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count(QuizAnswer.id)).where(QuizAnswer.user_id == user_id)
        )
        return int(result.scalar_one())

    async def average_correct(self, *, user_id: int) -> float | None:
        result = await self._session.execute(
            select(func.avg(cast(QuizAnswer.is_correct, Integer))).where(
                QuizAnswer.user_id == user_id
            )
        )
        value = result.scalar_one()
        return float(value) if value is not None else None


class FlashcardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        card = Flashcard(
            user_id=user_id, front=front, back=back, concept_id=concept_id, source=source, difficulty=difficulty
        )
        self._session.add(card)
        await self._session.flush()
        return card

    async def get(self, *, user_id: int, card_id: int) -> Flashcard | None:
        result = await self._session.execute(
            select(Flashcard).where(Flashcard.id == card_id, Flashcard.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_due(self, *, user_id: int, now: datetime, limit: int = 10) -> list[Flashcard]:
        result = await self._session.execute(
            select(Flashcard)
            .where(
                Flashcard.user_id == user_id,
                Flashcard.next_review_at.is_not(None),
                Flashcard.next_review_at <= now,
            )
            .order_by(Flashcard.next_review_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_new(self, *, user_id: int, limit: int = 10) -> list[Flashcard]:
        result = await self._session.execute(
            select(Flashcard)
            .where(Flashcard.user_id == user_id, Flashcard.next_review_at.is_(None))
            .order_by(Flashcard.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_review(
        self, card: Flashcard, *, status, last_reviewed_at: datetime, next_review_at: datetime | None
    ) -> Flashcard:
        card.status = status
        card.last_reviewed_at = last_reviewed_at
        card.next_review_at = next_review_at
        await self._session.flush()
        return card


class BookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, user_id: int, title: str, author: str | None = None, source: str | None = None
    ) -> Book:
        book = Book(user_id=user_id, title=title, author=author, source=source)
        self._session.add(book)
        await self._session.flush()
        return book

    async def get(self, *, user_id: int, book_id: int) -> Book | None:
        result = await self._session.execute(
            select(Book).where(Book.id == book_id, Book.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_pending(self, *, user_id: int) -> Book | None:
        result = await self._session.execute(
            select(Book)
            .where(Book.user_id == user_id, Book.status == BookStatus.PENDING)
            .order_by(Book.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list(self, *, user_id: int) -> list[Book]:
        result = await self._session.execute(
            select(Book).where(Book.user_id == user_id).order_by(Book.id.desc())
        )
        return list(result.scalars().all())

    async def update(self, book: Book, **fields: Any) -> Book:
        for field, value in fields.items():
            setattr(book, field, value)
        await self._session.flush()
        return book


class ChapterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        book_id: int,
        user_id: int,
        number: str | None,
        title: str,
        order_index: int,
        content: str | None = None,
    ) -> Chapter:
        chapter = Chapter(
            book_id=book_id, user_id=user_id, number=number, title=title, order_index=order_index, content=content
        )
        self._session.add(chapter)
        await self._session.flush()
        return chapter

    async def list_for_book(self, *, book_id: int) -> list[Chapter]:
        result = await self._session.execute(
            select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order_index)
        )
        return list(result.scalars().all())

    async def get(self, *, user_id: int, chapter_id: int) -> Chapter | None:
        result = await self._session.execute(
            select(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update(self, chapter: Chapter, **fields: Any) -> Chapter:
        for field, value in fields.items():
            setattr(chapter, field, value)
        await self._session.flush()
        return chapter
