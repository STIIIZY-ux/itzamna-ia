"""Modelo de flashcard."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import FlashcardStatus

if TYPE_CHECKING:
    from .concept import Concept
    from .user import User


class Flashcard(Base):
    """Tarjeta de repaso (frente/reverso) con repetición espaciada."""

    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_id: Mapped[int | None] = mapped_column(ForeignKey("concepts.id", ondelete="SET NULL"))
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer, default=2, server_default="2", nullable=False)
    status: Mapped[FlashcardStatus] = mapped_column(
        Enum(
            FlashcardStatus,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=FlashcardStatus.NEW,
        server_default=FlashcardStatus.NEW.value,
        nullable=False,
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    concept: Mapped[Concept | None] = relationship()
    user: Mapped[User] = relationship()
