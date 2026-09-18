"""Servicio de planificación (planner determinista sobre las tareas)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import session_scope
from app.domain.enums import RiskLevel, TaskStatus
from app.planner.engine import next_task
from app.planner.models import PlannerTask, TaskRecommendation
from app.planner.risk import assess_risk
from app.repositories.accountability import AccountabilityRepository
from app.repositories.commitments import CommitmentRepository
from app.repositories.tasks import TaskRepository

_TERMINAL = {TaskStatus.TERMINADA, TaskStatus.ENTREGADA}


@dataclass(frozen=True)
class StatusSummary:
    pending_count: int
    next_title: str | None
    next_due: datetime | None
    next_risk: RiskLevel | None
    active_commitment_title: str | None
    rescue_candidates: int


class PlanningService:
    """Une el planner con las tareas del usuario."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def pending_tasks(self, user_id: int) -> list[PlannerTask]:
        async with session_scope(self._session_factory) as session:
            tasks = await TaskRepository(session).list_tasks(user_id=user_id)
        return [PlannerTask.from_orm(t) for t in tasks if t.status not in _TERMINAL]

    async def next_recommendation(
        self, user_id: int, now: datetime | None = None
    ) -> TaskRecommendation | None:
        tasks = await self.pending_tasks(user_id)
        return next_task(tasks, now or datetime.now(timezone.utc))

    async def status_summary(
        self, user_id: int, now: datetime | None = None
    ) -> StatusSummary:
        now = now or datetime.now(timezone.utc)
        tasks = await self.pending_tasks(user_id)
        recommendation = next_task(tasks, now)
        next_risk = assess_risk(recommendation.task, now) if recommendation else None

        async with session_scope(self._session_factory) as session:
            active = await CommitmentRepository(session).list_active_for_user(user_id=user_id)
            rescue = await AccountabilityRepository(session).list_rescue_candidates(
                user_id=user_id
            )

        task_by_id = {t.id: t for t in tasks}
        commitment_title = None
        for commitment in active:
            task = task_by_id.get(commitment.task_id)
            if task is not None:
                commitment_title = task.title
                break

        return StatusSummary(
            pending_count=len(tasks),
            next_title=recommendation.task.title if recommendation else None,
            next_due=recommendation.task.due_at if recommendation else None,
            next_risk=next_risk,
            active_commitment_title=commitment_title,
            rescue_candidates=len(rescue),
        )
