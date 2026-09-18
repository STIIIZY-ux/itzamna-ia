"""Repositorio de trabajos programados (scheduler persistente)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScheduledJob
from app.domain.enums import JobKind, JobStatus


class ScheduledJobRepository:
    """Acceso a datos de :class:`ScheduledJob`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        """Crea un job de forma idempotente por ``dedup_key``.

        Devuelve ``None`` si ya existía un job con la misma ``dedup_key``.
        """
        stmt = (
            pg_insert(ScheduledJob)
            .values(
                user_id=user_id,
                kind=kind,
                scheduled_at=scheduled_at,
                dedup_key=dedup_key,
                task_id=task_id,
                payload=payload,
                status=JobStatus.PENDING,
            )
            .on_conflict_do_nothing(index_elements=["dedup_key"])
            .returning(ScheduledJob.id)
        )
        job_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if job_id is None:
            return None
        await self._session.flush()
        return await self._session.get(ScheduledJob, job_id)

    async def claim_due(self, *, now: datetime, limit: int) -> list[ScheduledJob]:
        """Reclama jobs pendientes y vencidos de forma atómica (SKIP LOCKED)."""
        stmt = (
            select(ScheduledJob)
            .where(ScheduledJob.status == JobStatus.PENDING, ScheduledJob.scheduled_at <= now)
            .order_by(ScheduledJob.scheduled_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list((await self._session.execute(stmt)).scalars().all())
        for job in jobs:
            job.status = JobStatus.CLAIMED
            job.claimed_at = now
            job.attempts += 1
        await self._session.flush()
        return jobs

    async def mark_sent(self, job_id: int) -> None:
        job = await self._session.get(ScheduledJob, job_id)
        if job is not None:
            job.status = JobStatus.SENT
            job.sent_at = datetime.now().astimezone()
            await self._session.flush()

    async def mark_failed(self, job_id: int) -> None:
        job = await self._session.get(ScheduledJob, job_id)
        if job is not None:
            job.status = JobStatus.FAILED
            await self._session.flush()

    async def recover_stale(self, *, stale_before: datetime) -> int:
        """Devuelve a ``pending`` los jobs reclamados que quedaron abandonados."""
        result = await self._session.execute(
            update(ScheduledJob)
            .where(
                ScheduledJob.status == JobStatus.CLAIMED,
                ScheduledJob.claimed_at < stale_before,
            )
            .values(status=JobStatus.PENDING, claimed_at=None)
        )
        await self._session.flush()
        return int(getattr(result, "rowcount", 0) or 0)
