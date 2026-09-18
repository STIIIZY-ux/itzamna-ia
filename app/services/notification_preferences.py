"""Servicio de preferencias de notificación (modo, pausa, horario)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import NotificationPreferences
from app.db.session import session_scope
from app.domain.enums import AccountabilityMode
from app.repositories.notification_preferences import NotificationPreferencesRepository


class NotificationPreferencesService:
    """Gestión de modo, pausa y límites de notificación del usuario."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_or_create(self, user_id: int) -> NotificationPreferences:
        async with session_scope(self._session_factory) as session:
            return await NotificationPreferencesRepository(session).get_or_create(user_id)

    async def get(self, user_id: int) -> NotificationPreferences:
        async with session_scope(self._session_factory) as session:
            return await NotificationPreferencesRepository(session).get_or_create(user_id)

    async def set_mode(self, user_id: int, mode: AccountabilityMode) -> NotificationPreferences:
        async with session_scope(self._session_factory) as session:
            repo = NotificationPreferencesRepository(session)
            record = await repo.get_or_create(user_id)
            return await repo.update(record, mode=mode)

    async def pause(
        self, user_id: int, *, minutes: int, now: datetime | None = None
    ) -> NotificationPreferences:
        base = now or datetime.now(timezone.utc)
        paused_until = base + timedelta(minutes=minutes)
        async with session_scope(self._session_factory) as session:
            repo = NotificationPreferencesRepository(session)
            record = await repo.get_or_create(user_id)
            return await repo.update(record, paused_until=paused_until)

    async def resume(self, user_id: int) -> NotificationPreferences:
        async with session_scope(self._session_factory) as session:
            repo = NotificationPreferencesRepository(session)
            record = await repo.get_or_create(user_id)
            return await repo.update(record, paused_until=None)

    async def is_paused(self, user_id: int, *, now: datetime | None = None) -> bool:
        record = await self.get(user_id)
        if record.paused_until is None:
            return False
        return record.paused_until > (now or datetime.now(timezone.utc))

    async def is_within_active_hours(
        self, user_id: int, *, now: datetime, timezone_name: str
    ) -> bool:
        record = await self.get(user_id)
        from zoneinfo import ZoneInfo

        try:
            zone = ZoneInfo(timezone_name)
        except Exception:  # noqa: BLE001
            return True
        local = now.astimezone(zone)
        if record.active_hour_start <= record.active_hour_end:
            return record.active_hour_start <= local.hour < record.active_hour_end
        # ventana que cruza medianoche
        return local.hour >= record.active_hour_start or local.hour < record.active_hour_end
