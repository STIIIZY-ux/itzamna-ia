"""Servicio del scheduler persistente."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ScheduledJob
from app.db.session import session_scope
from app.domain.enums import JobKind
from app.repositories.scheduled_jobs import ScheduledJobRepository


class SchedulerService:
    """Operaciones sobre trabajos programados persistentes."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def schedule(
        self,
        *,
        user_id: int,
        kind: JobKind,
        scheduled_at: datetime,
        dedup_key: str,
        task_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ScheduledJob | None:
        async with session_scope(self._session_factory) as session:
            return await ScheduledJobRepository(session).schedule(
                user_id=user_id,
                kind=kind,
                scheduled_at=scheduled_at,
                dedup_key=dedup_key,
                task_id=task_id,
                payload=payload,
            )

    async def claim_due(self, *, now: datetime, limit: int) -> list[ScheduledJob]:
        async with session_scope(self._session_factory) as session:
            return await ScheduledJobRepository(session).claim_due(now=now, limit=limit)

    async def mark_sent(self, job_id: int) -> None:
        async with session_scope(self._session_factory) as session:
            await ScheduledJobRepository(session).mark_sent(job_id)

    async def mark_failed(self, job_id: int) -> None:
        async with session_scope(self._session_factory) as session:
            await ScheduledJobRepository(session).mark_failed(job_id)

    async def recover_stale(self, *, stale_before: datetime) -> int:
        async with session_scope(self._session_factory) as session:
            return await ScheduledJobRepository(session).recover_stale(stale_before=stale_before)
