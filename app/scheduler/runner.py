"""Ejecutor del scheduler: bucle que reclama y despacha jobs vencidos."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from app.db.models import ScheduledJob

from .service import SchedulerService

logger = logging.getLogger(__name__)


class SchedulerRunner:
    """Bucle de fondo que procesa jobs vencidos de forma idempotente.

    ``dispatch`` es un callable async ``(job) -> bool`` inyectado (envía el
    mensaje). Esto desacopla el scheduler de Telegram y lo hace testeable.
    """

    def __init__(
        self,
        *,
        scheduler: SchedulerService,
        dispatch: Callable[[ScheduledJob], Awaitable[bool]],
        poll_interval_seconds: float = 30.0,
        stale_claim_seconds: float = 300.0,
        claim_batch_size: int = 20,
    ) -> None:
        self._scheduler = scheduler
        self._dispatch = dispatch
        self._poll_interval = poll_interval_seconds
        self._stale_claim_seconds = stale_claim_seconds
        self._claim_batch_size = claim_batch_size
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def tick(self) -> int:
        """Ejecuta una pasada de procesamiento. Devuelve jobs despachados."""
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=self._stale_claim_seconds)
        await self._scheduler.recover_stale(stale_before=stale_before)

        jobs = await self._scheduler.claim_due(now=now, limit=self._claim_batch_size)
        dispatched = 0
        for job in jobs:
            sent = False
            try:
                sent = await self._dispatch(job)
            except Exception:
                logger.exception("Error despachando job %s", job.id)
            if sent:
                await self._scheduler.mark_sent(job.id)
                dispatched += 1
            else:
                await self._scheduler.mark_failed(job.id)
        return dispatched

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001 - bucle resiliente
                logger.error("Error en el scheduler: %s", exc)
            await asyncio.sleep(self._poll_interval)
