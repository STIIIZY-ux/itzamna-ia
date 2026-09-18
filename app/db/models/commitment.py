"""Modelo de compromiso (accountability)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import CommitmentStatus

if TYPE_CHECKING:
    from .task import Task
    from .user import User


class Commitment(Base):
    """Compromiso de un usuario respecto a una tarea (accountability)."""

    __tablename__ = "commitments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[CommitmentStatus] = mapped_column(
        Enum(
            CommitmentStatus,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=CommitmentStatus.ACTIVO,
        server_default=CommitmentStatus.ACTIVO.value,
        nullable=False,
    )
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="commitments")
    user: Mapped[User] = relationship(back_populates="commitments")
