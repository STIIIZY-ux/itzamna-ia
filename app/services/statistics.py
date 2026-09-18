"""Estadísticas del sistema (deterministas, sin IA)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import session_scope
from app.domain.enums import TaskStatus
from app.repositories.learning import ConceptRepository, QuizAnswerRepository
from app.repositories.tasks import TaskRepository

_TERMINAL = {TaskStatus.TERMINADA, TaskStatus.ENTREGADA}
_WEAK_THRESHOLD = 0.6


@dataclass(frozen=True)
class PeriodStats:
    tasks_total: int
    tasks_completed: int
    tasks_overdue: int
    on_time: int
    quizzes_taken: int
    quiz_avg: float | None
    avg_mastery: float | None
    weak_concepts: int


class StatisticsService:
    """Agrega métricas del usuario (totales, semanal, diario)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def totals(self, user_id: int, now: datetime | None = None) -> PeriodStats:
        return await self._compute(user_id=user_id, since=None, now=now)

    async def weekly(self, user_id: int, now: datetime | None = None) -> PeriodStats:
        now = now or datetime.now(timezone.utc)
        return await self._compute(user_id=user_id, since=now - timedelta(days=7), now=now)

    async def daily(self, user_id: int, date: datetime | None = None) -> PeriodStats:
        day = date or datetime.now(timezone.utc)
        start = datetime.combine(day.date(), time.min, tzinfo=day.tzinfo)
        end = datetime.combine(day.date(), time.max, tzinfo=day.tzinfo)
        return await self._compute(user_id=user_id, since=start, until=end)

    async def _compute(
        self,
        *,
        user_id: int,
        since: datetime | None,
        now: datetime | None = None,
        until: datetime | None = None,
    ) -> PeriodStats:
        now = now or datetime.now(timezone.utc)

        async with session_scope(self._session_factory) as session:
            tasks = await TaskRepository(session).list_tasks(user_id=user_id, limit=1000)
            quiz_taken = await QuizAnswerRepository(session).count_for_user(user_id=user_id)
            quiz_avg = await QuizAnswerRepository(session).average_correct(user_id=user_id)
            avg_mastery = await ConceptRepository(session).average_mastery(user_id=user_id)
            weak = await ConceptRepository(session).list_weak(user_id=user_id, threshold=_WEAK_THRESHOLD)

        scoped = tasks
        if since is not None:
            scoped = [t for t in tasks if t.due_at is not None and t.due_at >= since]
        if until is not None:
            scoped = [t for t in scoped if t.due_at is not None and t.due_at <= until]

        completed = [t for t in scoped if t.status in _TERMINAL]
        overdue = [t for t in scoped if t.status not in _TERMINAL and t.due_at is not None and t.due_at < now]
        on_time = sum(1 for t in completed if t.due_at is None or t.due_at >= now)

        return PeriodStats(
            tasks_total=len(scoped),
            tasks_completed=len(completed),
            tasks_overdue=len(overdue),
            on_time=on_time,
            quizzes_taken=quiz_taken,
            quiz_avg=quiz_avg,
            avg_mastery=avg_mastery,
            weak_concepts=len(weak),
        )
