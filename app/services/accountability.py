"""Servicio de accountability: flujo de estados y compromisos."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Accountability, Commitment
from app.db.session import session_scope
from app.domain.enums import (
    AccountabilityMode,
    AccountabilityState,
    JobKind,
)
from app.domain.errors import NotFoundError
from app.repositories.accountability import AccountabilityRepository
from app.repositories.commitments import CommitmentRepository
from app.repositories.notification_preferences import NotificationPreferencesRepository
from app.repositories.scheduled_jobs import ScheduledJobRepository
from app.repositories.tasks import TaskRepository


class AccountabilityService:
    """Flujo de accountability (TRYHARD por defecto) sobre tareas."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        tryhard_interval_minutes: int = 120,
        guerra_interval_minutes: int = 30,
    ) -> None:
        self._session_factory = session_factory
        self._tryhard_interval_minutes = tryhard_interval_minutes
        self._guerra_interval_minutes = guerra_interval_minutes

    async def get_state(self, *, user_id: int, task_id: int) -> Accountability | None:
        async with session_scope(self._session_factory) as session:
            return await AccountabilityRepository(session).get(user_id=user_id, task_id=task_id)

    async def get_or_create_state(self, *, user_id: int, task_id: int) -> Accountability:
        async with session_scope(self._session_factory) as session:
            return await AccountabilityRepository(session).get_or_create(
                user_id=user_id, task_id=task_id
            )

    async def record_commitment(
        self, *, user_id: int, task_id: int, note: str | None = None
    ) -> Commitment:
        """Registra un compromiso explícito (idempotente por tarea)."""
        async with session_scope(self._session_factory) as session:
            task = await TaskRepository(session).get(user_id=user_id, task_id=task_id)
            if task is None:
                raise NotFoundError(f"Tarea {task_id} no encontrada")

            existing = await CommitmentRepository(session).get_active_for_task(
                user_id=user_id, task_id=task_id
            )
            if existing is not None:
                return existing

            commitment = await CommitmentRepository(session).create(
                task_id=task_id, user_id=user_id, note=note
            )
            acc = await AccountabilityRepository(session).get_or_create(
                user_id=user_id, task_id=task_id
            )
            await AccountabilityRepository(session).update(
                acc, state=AccountabilityState.COMMITTED, rescue_candidate=False
            )
            return commitment

    async def mark_evidence_requested(self, *, user_id: int, task_id: int) -> Accountability:
        async with session_scope(self._session_factory) as session:
            acc = await AccountabilityRepository(session).get_or_create(
                user_id=user_id, task_id=task_id
            )
            return await AccountabilityRepository(session).update(
                acc, state=AccountabilityState.AWAITING_EVIDENCE
            )

    async def mark_completed(self, *, user_id: int, task_id: int) -> Accountability:
        async with session_scope(self._session_factory) as session:
            acc = await AccountabilityRepository(session).get_or_create(
                user_id=user_id, task_id=task_id
            )
            return await AccountabilityRepository(session).update(
                acc, state=AccountabilityState.COMPLETED, rescue_candidate=False
            )

    async def set_rescue_candidate(
        self, *, user_id: int, task_id: int, value: bool
    ) -> Accountability:
        async with session_scope(self._session_factory) as session:
            acc = await AccountabilityRepository(session).get_or_create(
                user_id=user_id, task_id=task_id
            )
            return await AccountabilityRepository(session).update(acc, rescue_candidate=value)

    async def schedule_follow_up(
        self, *, user_id: int, task_id: int, now: datetime, timezone_name: str
    ) -> bool:
        """Programa la siguiente insistencia si corresponde.

        Devuelve ``True`` si se programó un nudge; ``False`` si el usuario está
        en silencio/pausa, ya se comprometió, está fuera del horario activo o
        alcanzó el límite diario.
        """
        async with session_scope(self._session_factory) as session:
            acc = await AccountabilityRepository(session).get_or_create(
                user_id=user_id, task_id=task_id
            )
            prefs = await NotificationPreferencesRepository(session).get_or_create(user_id)

            if prefs.mode is AccountabilityMode.SILENCIO:
                return False
            if prefs.paused_until is not None and prefs.paused_until > now:
                return False
            if acc.state in (
                AccountabilityState.COMMITTED,
                AccountabilityState.AWAITING_EVIDENCE,
                AccountabilityState.COMPLETED,
            ):
                return False
            if not _within_active_hours(now, timezone_name, prefs.active_hour_start, prefs.active_hour_end):
                return False
            if acc.reminder_count >= prefs.max_reminders_per_day:
                return False

            interval = (
                self._guerra_interval_minutes
                if prefs.mode is AccountabilityMode.GUERRA
                else self._tryhard_interval_minutes
            )
            next_at = now + timedelta(minutes=interval)
            attempt = acc.reminder_count + 1

            job = await ScheduledJobRepository(session).schedule(
                user_id=user_id,
                kind=JobKind.NUDGE,
                scheduled_at=next_at,
                dedup_key=f"nudge:{task_id}:{attempt}",
                task_id=task_id,
                payload={"task_id": task_id},
            )
            await AccountabilityRepository(session).update(
                acc,
                state=AccountabilityState.AWAITING_COMMITMENT,
                last_reminder_at=now,
                next_reminder_at=next_at,
                increment_reminder_count=True,
            )
            return job is not None


def _within_active_hours(
    now: datetime, timezone_name: str, start_hour: int, end_hour: int
) -> bool:
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return True
    hour = now.astimezone(zone).hour
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour
