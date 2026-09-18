"""Modelo del estado de accountability de una tarea."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import AccountabilityMode, AccountabilityState

if TYPE_CHECKING:
    from .task import Task
    from .user import User


class Accountability(Base):
    """Estado persistente del flujo de accountability de una tarea.

    Una fila por tarea (por usuario). ``rescue_candidate`` es una señal que la
    Etapa 6 (modo rescate) podrá consumir.
    """

    __tablename__ = "accountability"
    __table_args__ = (UniqueConstraint("task_id", name="uq_accountability_task_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    state: Mapped[AccountabilityState] = mapped_column(
        Enum(
            AccountabilityState,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=AccountabilityState.PENDING_REMINDER,
        server_default=AccountabilityState.PENDING_REMINDER.value,
        nullable=False,
    )
    mode: Mapped[AccountabilityMode] = mapped_column(
        Enum(
            AccountabilityMode,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=AccountabilityMode.TRYHARD,
        server_default=AccountabilityMode.TRYHARD.value,
        nullable=False,
    )
    reminder_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rescue_candidate: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    task: Mapped[Task] = relationship()
    user: Mapped[User] = relationship()
