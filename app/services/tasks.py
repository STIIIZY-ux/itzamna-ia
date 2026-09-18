"""Servicio de tareas: núcleo de negocio del sistema de tareas."""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Task
from app.db.session import session_scope
from app.domain.enums import HistoryEventType, TaskPriority, TaskSource, TaskStatus
from app.domain.errors import InvalidStateTransitionError, NotFoundError
from app.domain.state_machine import can_transition
from app.repositories.subjects import SubjectRepository
from app.repositories.tasks import TaskRepository

#: Campos editables vía :meth:`TaskService.update_task`.
_EDITABLE_FIELDS = frozenset(
    {
        "title",
        "description",
        "instructions",
        "due_at",
        "timezone",
        "priority",
        "estimated_minutes",
        "subject_id",
    }
)


class TaskService:
    """Casos de uso sobre tareas académicas."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_task(
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
        async with session_scope(self._session_factory) as session:
            if subject_id is not None:
                subject = await SubjectRepository(session).get(
                    user_id=user_id, subject_id=subject_id
                )
                if subject is None:
                    raise NotFoundError(f"Materia {subject_id} no encontrada")

            repo = TaskRepository(session)
            task = await repo.create(
                user_id=user_id,
                title=title,
                subject_id=subject_id,
                description=description,
                instructions=instructions,
                due_at=due_at,
                timezone=timezone,
                source=source,
                source_event_id=source_event_id,
                priority=priority,
                estimated_minutes=estimated_minutes,
            )
            await repo.add_history(task, HistoryEventType.CREADA)
            return task

    async def get_task(self, *, user_id: int, task_id: int) -> Task:
        async with session_scope(self._session_factory) as session:
            repo = TaskRepository(session)
            task = await repo.get(user_id=user_id, task_id=task_id)
            if task is None:
                raise NotFoundError(f"Tarea {task_id} no encontrada")
            return task

    async def list_tasks(
        self,
        *,
        user_id: int,
        status: TaskStatus | None = None,
        subject_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        async with session_scope(self._session_factory) as session:
            repo = TaskRepository(session)
            return await repo.list_tasks(
                user_id=user_id,
                status=status,
                subject_id=subject_id,
                limit=limit,
                offset=offset,
            )

    async def change_status(
        self, *, user_id: int, task_id: int, new_status: TaskStatus
    ) -> Task:
        async with session_scope(self._session_factory) as session:
            repo = TaskRepository(session)
            task = await repo.get(user_id=user_id, task_id=task_id)
            if task is None:
                raise NotFoundError(f"Tarea {task_id} no encontrada")

            if not can_transition(task.status, new_status):
                raise InvalidStateTransitionError(task.status.value, new_status.value)

            old_status = task.status
            task.status = new_status
            await repo.add_history(
                task,
                HistoryEventType.ESTADO_CAMBIADO,
                from_value=old_status.value,
                to_value=new_status.value,
            )
            return task

    async def update_task(self, *, user_id: int, task_id: int, **fields: Any) -> Task:
        unknown = set(fields) - _EDITABLE_FIELDS
        if unknown:
            raise ValueError(f"Campos no editables: {sorted(unknown)}")

        async with session_scope(self._session_factory) as session:
            repo = TaskRepository(session)
            task = await repo.get(user_id=user_id, task_id=task_id)
            if task is None:
                raise NotFoundError(f"Tarea {task_id} no encontrada")

            if "subject_id" in fields and fields["subject_id"] is not None:
                subject = await SubjectRepository(session).get(
                    user_id=user_id, subject_id=fields["subject_id"]
                )
                if subject is None:
                    raise NotFoundError(f"Materia {fields['subject_id']} no encontrada")

            old_priority = task.priority
            old_due_at = task.due_at

            for field, value in fields.items():
                setattr(task, field, value)

            if "priority" in fields and fields["priority"] != old_priority:
                await repo.add_history(
                    task,
                    HistoryEventType.PRIORIDAD_CAMBIADA,
                    from_value=old_priority.value,
                    to_value=task.priority.value,
                )
            if "due_at" in fields and fields["due_at"] != old_due_at:
                await repo.add_history(
                    task,
                    HistoryEventType.FECHA_CAMBIADA,
                    from_value=_isoformat(old_due_at),
                    to_value=_isoformat(task.due_at),
                )
            if fields and not _only_history_fields(fields):
                await repo.add_history(task, HistoryEventType.ACTUALIZADA)
            return task

    async def delete_task(self, *, user_id: int, task_id: int) -> bool:
        async with session_scope(self._session_factory) as session:
            repo = TaskRepository(session)
            return await repo.delete(user_id=user_id, task_id=task_id)


def _isoformat(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _only_history_fields(fields: dict[str, Any]) -> bool:
    """Indica si ``fields`` solo contiene cambios ya reflejados en el historial."""
    return set(fields) <= {"priority", "due_at"}
