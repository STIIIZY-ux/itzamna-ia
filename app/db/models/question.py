"""Modelo de pregunta académica."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import QuestionType

if TYPE_CHECKING:
    from .book import Book
    from .chapter import Chapter
    from .concept import Concept
    from .subject import Subject
    from .user import User


class Question(Base):
    """Pregunta académica persistida."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_id: Mapped[int | None] = mapped_column(ForeignKey("concepts.id", ondelete="SET NULL"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"))
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"))
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(
            QuestionType,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    options: Mapped[list[str] | None] = mapped_column(JSONB)
    correct_index: Mapped[int | None] = mapped_column(Integer)
    difficulty: Mapped[int] = mapped_column(Integer, default=2, server_default="2", nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    source_ref: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    concept: Mapped[Concept | None] = relationship()
    subject: Mapped[Subject | None] = relationship()
    book: Mapped[Book | None] = relationship()
    chapter: Mapped[Chapter | None] = relationship()
    user: Mapped[User] = relationship()
