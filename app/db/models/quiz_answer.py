"""Modelo de respuesta a una pregunta de quiz (intento)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from .question import Question
    from .quiz import Quiz
    from .user import User


class QuizAnswer(Base):
    """Respuesta del usuario a una pregunta. Conserva la respuesta original."""

    __tablename__ = "quiz_answers"
    __table_args__ = (
        UniqueConstraint("quiz_id", "question_id", "user_id", name="uq_quiz_answers_once"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    quiz_id: Mapped[int | None] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    quiz: Mapped[Quiz | None] = relationship()
    question: Mapped[Question] = relationship()
    user: Mapped[User] = relationship()
