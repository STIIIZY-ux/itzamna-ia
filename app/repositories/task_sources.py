"""Repositorio del mapeo tarea -> eventos externos."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task, TaskEventSource


class TaskSourceRepository:
    """Acceso a datos de :class:`TaskEventSource`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_event(self, source: str, source_event_id: str) -> TaskEventSource | None:
        result = await self._session.execute(
            select(TaskEventSource).where(
                TaskEventSource.source == source,
                TaskEventSource.source_event_id == source_event_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_source_for_user(self, user_id: int, source: str) -> list[TaskEventSource]:
        result = await self._session.execute(
            select(TaskEventSource)
            .join(Task, Task.id == TaskEventSource.task_id)
            .where(Task.user_id == user_id, TaskEventSource.source == source)
        )
        return list(result.scalars().all())

    async def add(
        self, *, task_id: int, source: str, source_event_id: str, is_primary: bool = False
    ) -> TaskEventSource:
        mapping = TaskEventSource(
            task_id=task_id,
            source=source,
            source_event_id=source_event_id,
            is_primary=is_primary,
        )
        self._session.add(mapping)
        await self._session.flush()
        return mapping
