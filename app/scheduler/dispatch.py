"""Despacho de jobs del scheduler hacia Telegram."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ScheduledJob
from app.db.session import session_scope
from app.domain.enums import JobKind
from app.repositories.tasks import TaskRepository
from app.repositories.users import UserRepository

from .messages import build_reminder_message

logger = logging.getLogger(__name__)


def make_dispatcher(
    send_message: Callable[[int, str], Awaitable[None]],
    session_factory: async_sessionmaker[AsyncSession],
    timezone: str,
    analyze_evidence: Callable[[ScheduledJob], Awaitable[bool]] | None = None,
) -> Callable[[ScheduledJob], Awaitable[bool]]:
    """Construye el callable de despacho del scheduler.

    ``send_message`` envía texto a un ``chat_id`` (p. ej. ``bot.send_message``).
    ``analyze_evidence`` procesa los jobs de análisis de evidencia (visión).
    """

    async def dispatch(job: ScheduledJob) -> bool:
        if job.kind is JobKind.ANALYZE_EVIDENCE:
            if analyze_evidence is None:
                return False
            return await analyze_evidence(job)

        payload = job.payload or {}
        task_id = job.task_id or payload.get("task_id")
        if task_id is None:
            logger.warning("Job %s sin task_id", job.id)
            return False

        async with session_scope(session_factory) as session:
            task = await TaskRepository(session).get(user_id=job.user_id, task_id=task_id)
            user = await UserRepository(session).get(job.user_id)

        if task is None or user is None:
            logger.warning("Job %s: tarea/usuario no encontrado", job.id)
            return False

        text = build_reminder_message(job.kind, task, timezone=timezone)
        await send_message(user.telegram_id, text)
        return True

    return dispatch
