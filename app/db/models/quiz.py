"""Modelos de quiz y su relación con preguntas."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import QuizStatus, QuizType

if TYPE_CHECKING:
    from .question import Question
    from .user import User


class Quiz(Base):
    """Quiz persistente (por tarea, materia, concepto, capítulo o acumulativo)."""

    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    quiz_type: Mapped[QuizType] = mapped_column(
        Enum(
            QuizType,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[QuizStatus] = mapped_column(
        Enum(
            QuizStatus,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=QuizStatus.DRAFT,
        server_default=QuizStatus.DRAFT.value,
        nullable=False,
    )
    score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    quiz_questions: Mapped[list[QuizQuestion]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="QuizQuestion.order_index"
    )


class QuizQuestion(Base):
    """Pregunta dentro de un quiz, con orden."""

    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "question_id", name="uq_quiz_questions_quiz_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    quiz: Mapped[Quiz] = relationship(back_populates="quiz_questions")
    question: Mapped[Question] = relationship()
