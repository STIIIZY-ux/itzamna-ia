"""Modelo de preferencias de notificación del usuario."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import AccountabilityMode

if TYPE_CHECKING:
    from .user import User


class NotificationPreferences(Base):
    """Preferencias de notificación (modo, pausa, horario, intensidad)."""

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
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
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_hour_start: Mapped[int] = mapped_column(Integer, default=9, server_default="9", nullable=False)
    active_hour_end: Mapped[int] = mapped_column(Integer, default=21, server_default="21", nullable=False)
    max_reminders_per_day: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
