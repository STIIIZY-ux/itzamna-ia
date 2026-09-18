"""Repositorio de preferencias de notificación."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NotificationPreferences
from app.domain.enums import AccountabilityMode

_UNSET: Any = object()


class NotificationPreferencesRepository:
    """Acceso a datos de :class:`NotificationPreferences`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> NotificationPreferences | None:
        result = await self._session.execute(
            select(NotificationPreferences).where(NotificationPreferences.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int) -> NotificationPreferences:
        record = await self.get(user_id)
        if record is None:
            record = NotificationPreferences(user_id=user_id)
            self._session.add(record)
            await self._session.flush()
        return record

    async def update(
        self,
        record: NotificationPreferences,
        *,
        mode: AccountabilityMode | None = None,
        paused_until: datetime | None = _UNSET,
        active_hour_start: int | None = None,
        active_hour_end: int | None = None,
        max_reminders_per_day: int | None = None,
    ) -> NotificationPreferences:
        if mode is not None:
            record.mode = mode
        if paused_until is not _UNSET:
            record.paused_until = paused_until
        if active_hour_start is not None:
            record.active_hour_start = active_hour_start
        if active_hour_end is not None:
            record.active_hour_end = active_hour_end
        if max_reminders_per_day is not None:
            record.max_reminders_per_day = max_reminders_per_day
        await self._session.flush()
        return record
