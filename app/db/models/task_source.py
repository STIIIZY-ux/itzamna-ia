"""Modelo de mapeo tarea -> eventos externos (deduplicación)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from .task import Task


class TaskEventSource(Base):
    """Asocia una tarea a uno o más eventos externos.

    Permite consolidar varios eventos externos duplicados (p. ej. dos eventos
    idénticos de Google Calendar con distinto ``event_id``) en una sola tarea,
    conservando el rastro de todos los ``source_event_id``.
    """

    __tablename__ = "task_sources"
    __table_args__ = (
        UniqueConstraint("source", "source_event_id", name="uq_task_sources_source_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="sources")
