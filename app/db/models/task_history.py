"""Modelo de historial de tareas."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import HistoryEventType

if TYPE_CHECKING:
    from .task import Task


class TaskHistory(Base):
    """Registro inmutable de un evento importante sobre una tarea."""

    __tablename__ = "task_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_type: Mapped[HistoryEventType] = mapped_column(
        Enum(
            HistoryEventType,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    from_value: Mapped[str | None] = mapped_column(String(255))
    to_value: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="history")
