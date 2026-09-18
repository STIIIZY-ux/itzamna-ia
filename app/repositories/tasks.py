"""Repositorio de tareas e historial."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Task, TaskHistory
from app.domain.enums import HistoryEventType, TaskPriority, TaskSource, TaskStatus


class TaskRepository:
    """Acceso a datos de :class:`Task`, siempre acotado por usuario."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        title: str,
        subject_id: int | None = None,
        description: str | None = None,
        instructions: str | None = None,
        due_at: datetime | None = None,
        timezone: str | None = None,
        source: TaskSource = TaskSource.MANUAL,
        source_event_id: str | None = None,
        priority: TaskPriority = TaskPriority.MEDIA,
        estimated_minutes: int | None = None,
    ) -> Task:
        task = Task(
            user_id=user_id,
            subject_id=subject_id,
            title=title,
            description=description,
            instructions=instructions,
            due_at=due_at,
            timezone=timezone,
            source=source,
            source_event_id=source_event_id,
            priority=priority,
            estimated_minutes=estimated_minutes,
            status=TaskStatus.PENDIENTE,
        )
        self._session.add(task)
        await self._session.flush()
        return task

    async def get(self, *, user_id: int, task_id: int) -> Task | None:
        result = await self._session.execute(
            select(Task)
            .options(selectinload(Task.history), selectinload(Task.subject))
            .where(Task.id == task_id, Task.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_tasks(
        self,
        *,
        user_id: int,
        status: TaskStatus | None = None,
        subject_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        stmt = (
            select(Task)
            .options(selectinload(Task.history), selectinload(Task.subject))
            .where(Task.user_id == user_id)
        )
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if subject_id is not None:
            stmt = stmt.where(Task.subject_id == subject_id)
        stmt = stmt.order_by(Task.due_at.asc().nulls_last(), Task.id).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_source_event_id(
        self, *, user_id: int, source: TaskSource, source_event_id: str
    ) -> Task | None:
        result = await self._session.execute(
            select(Task)
            .options(selectinload(Task.history), selectinload(Task.subject))
            .where(
                Task.user_id == user_id,
                Task.source == source,
                Task.source_event_id == source_event_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_source(self, *, user_id: int, source: TaskSource) -> list[Task]:
        result = await self._session.execute(
            select(Task)
            .options(selectinload(Task.history), selectinload(Task.subject))
            .where(Task.user_id == user_id, Task.source == source)
            .order_by(Task.id)
        )
        return list(result.scalars().all())

    async def delete(self, *, user_id: int, task_id: int) -> bool:
        task = await self.get(user_id=user_id, task_id=task_id)
        if task is None:
            return False
        await self._session.delete(task)
        await self._session.flush()
        return True

    async def add_history(
        self,
        task: Task,
        event_type: HistoryEventType,
        *,
        from_value: str | None = None,
        to_value: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskHistory:
        entry = TaskHistory(
            task_id=task.id,
            event_type=event_type,
            from_value=from_value,
            to_value=to_value,
            details=details,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
