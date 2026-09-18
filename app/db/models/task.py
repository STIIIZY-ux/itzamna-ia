"""Modelo de tarea: núcleo del sistema."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import TaskPriority, TaskSource, TaskStatus

if TYPE_CHECKING:
    from .commitment import Commitment
    from .resource import Resource
    from .subject import Subject
    from .task_history import TaskHistory
    from .task_source import TaskEventSource
    from .user import User


class Task(Base):
    """Tarea académica perteneciente a un usuario.

    ``source`` y ``source_event_id`` permiten asociar la tarea a una fuente
    externa (p. ej. ``google_calendar`` + id del evento) sin implementar la
    integración. La unicidad ``(source, source_event_id)`` da soporte a la
    futura deduplicación.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("source", "source_event_id", name="uq_tasks_source_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)

    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str | None] = mapped_column(String(64))

    source: Mapped[TaskSource] = mapped_column(
        Enum(
            TaskSource,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=TaskSource.MANUAL,
        server_default=TaskSource.MANUAL.value,
        nullable=False,
    )
    source_event_id: Mapped[str | None] = mapped_column(String(255), index=True)

    #: Última vez que la sincronización "vio" este evento externo.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Cuándo el evento externo dejó de existir en la fuente (marca, no borrado).
    removed_from_source_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    priority: Mapped[TaskPriority] = mapped_column(
        Enum(
            TaskPriority,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=TaskPriority.MEDIA,
        server_default=TaskPriority.MEDIA.value,
        nullable=False,
    )
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)

    #: Estimación ajustada por el histórico (no sobrescribe ``estimated_minutes``).
    adjusted_estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    estimate_basis: Mapped[str | None] = mapped_column(String(255))

    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=TaskStatus.PENDIENTE,
        server_default=TaskStatus.PENDIENTE.value,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="tasks")
    subject: Mapped[Subject | None] = relationship(back_populates="tasks")
    history: Mapped[list[TaskHistory]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskHistory.id",
    )
    commitments: Mapped[list[Commitment]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    resources: Mapped[list[Resource]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    sources: Mapped[list[TaskEventSource]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
