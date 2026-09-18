"""Modelo de libro académico."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import BookStatus

if TYPE_CHECKING:
    from .chapter import Chapter
    from .user import User


class Book(Base):
    """Libro o documento académico (PDF) con capítulos detectados."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(100))
    storage_key: Mapped[str | None] = mapped_column(String(255))
    num_chapters: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    status: Mapped[BookStatus] = mapped_column(
        Enum(
            BookStatus,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=BookStatus.PENDING,
        server_default=BookStatus.PENDING.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="book", cascade="all, delete-orphan", order_by="Chapter.order_index"
    )
