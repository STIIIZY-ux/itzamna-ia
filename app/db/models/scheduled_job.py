"""Modelo de trabajo programado (scheduler persistente)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import JobKind, JobStatus

if TYPE_CHECKING:
    from .task import Task
    from .user import User


class ScheduledJob(Base):
    """Trabajo persistente del scheduler (sobrevive reinicios).

    ``dedup_key`` es único y garantiza que el mismo recordatorio no se cree dos
    veces. El estado permite reclamar y recuperar trabajos tras un reinicio.
    """

    __tablename__ = "scheduled_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[JobKind] = mapped_column(
        Enum(JobKind, native_enum=False, length=50, validate_strings=True, values_callable=enum_values),
        nullable=False,
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=50, validate_strings=True, values_callable=enum_values),
        default=JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
        nullable=False,
    )
    dedup_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    task: Mapped[Task | None] = relationship()
