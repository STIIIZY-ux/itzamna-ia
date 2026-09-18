"""Modelo de capítulo de un libro."""

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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import ChapterStatus

if TYPE_CHECKING:
    from .book import Book
    from .user import User


class Chapter(Base):
    """Capítulo detectado de un libro, con contenido de texto extraído."""

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("book_id", "order_index", name="uq_chapters_book_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    number: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ChapterStatus] = mapped_column(
        Enum(
            ChapterStatus,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=ChapterStatus.PENDIENTE,
        server_default=ChapterStatus.PENDIENTE.value,
        nullable=False,
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    book: Mapped[Book] = relationship(back_populates="chapters")
    user: Mapped[User] = relationship()
