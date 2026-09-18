"""Programación de recordatorios a partir de las decisiones del planner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import session_scope
from app.domain.enums import JobKind, TaskStatus
from app.planner.engine import suggest_start_time
from app.planner.models import PlannerTask
from app.repositories.scheduled_jobs import ScheduledJobRepository
from app.repositories.tasks import TaskRepository

_DUE_REMINDER_LEAD_HOURS = 1
_TERMINAL = {TaskStatus.TERMINADA, TaskStatus.ENTREGADA}


class ReminderService:
    """Crea jobs de recordatorio persistentes a partir del planner."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def schedule_task_reminders(self, *, user_id: int, task_id: int) -> None:
        """Programa recordatorios de inicio y de entrega para una tarea."""
        now = datetime.now(timezone.utc)
        async with session_scope(self._session_factory) as session:
            task = await TaskRepository(session).get(user_id=user_id, task_id=task_id)
            if task is None:
                return
            repo = ScheduledJobRepository(session)
            planner_task = PlannerTask.from_orm(task)

            # Recordatorio de entrega (1 h antes del deadline).
            if task.due_at is not None:
                due_reminder = task.due_at - timedelta(hours=_DUE_REMINDER_LEAD_HOURS)
                if due_reminder > now:
                    await repo.schedule(
                        user_id=user_id,
                        kind=JobKind.DUE_REMINDER,
                        scheduled_at=due_reminder,
                        dedup_key=f"due:{task.id}",
                        task_id=task.id,
                        payload={"task_id": task.id},
                    )

            # Recordatorio de inicio (cuando conviene empezar).
            start = suggest_start_time(planner_task, now)
            if start is not None and start > now:
                await repo.schedule(
                    user_id=user_id,
                    kind=JobKind.START_REMINDER,
                    scheduled_at=start,
                    dedup_key=f"start:{task.id}",
                    task_id=task.id,
                    payload={"task_id": task.id},
                )

    async def schedule_for_user(self, *, user_id: int) -> None:
        """Programa recordatorios para todas las tareas pendientes del usuario."""
        async with session_scope(self._session_factory) as session:
            repo = TaskRepository(session)
            tasks = await repo.list_tasks(user_id=user_id)
        pending_ids = [t.id for t in tasks if t.status not in _TERMINAL]
        for task_id in pending_ids:
            await self.schedule_task_reminders(user_id=user_id, task_id=task_id)
