"""Servicio de sincronización Google Calendar -> tareas internas."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Task
from app.db.session import session_scope
from app.domain.enums import HistoryEventType, ResourceType, TaskSource
from app.integrations.google.classifier import is_task_event
from app.integrations.google.client import GoogleCalendarClient
from app.integrations.google.dedup import fingerprint
from app.integrations.google.normalizer import normalize_event
from app.integrations.google.schemas import NormalizedEvent
from app.repositories.resources import ResourceRepository
from app.repositories.subjects import SubjectRepository
from app.repositories.task_sources import TaskSourceRepository
from app.repositories.tasks import TaskRepository

#: Namespace arbitrario para el advisory lock por usuario.
_SYNC_LOCK_NAMESPACE = 0x49544E41  # "ITNA"


@dataclass
class SyncResult:
    """Resumen de una sincronización."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    consolidated: int = 0
    removed: int = 0
    skipped: int = 0

    def total_processed(self) -> int:
        return (
            self.created
            + self.updated
            + self.unchanged
            + self.consolidated
            + self.removed
        )


class CalendarSyncService:
    """Sincroniza eventos de Google Calendar con las tareas internas.

    El flujo es: cliente -> evento normalizado -> deduplicación -> TaskService/BD.
    La sincronización es idempotente y usa un advisory lock por usuario para
    evitar carreras entre sincronizaciones concurrentes.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        client: GoogleCalendarClient,
        timezone: str,
        calendar_id: str,
        time_window_days: int,
    ) -> None:
        self._session_factory = session_factory
        self._client = client
        self._timezone = timezone
        self._calendar_id = calendar_id
        self._time_window_days = time_window_days

    async def sync(self, user_id: int) -> SyncResult:
        now = datetime.now(timezone.utc)
        window = timedelta(days=self._time_window_days)
        raw_events = await self._client.list_events(
            user_id=user_id,
            calendar_id=self._calendar_id,
            time_min=now - window,
            time_max=now + window,
        )

        result = SyncResult()
        async with session_scope(self._session_factory) as session:
            await self._acquire_lock(session, user_id)

            task_repo = TaskRepository(session)
            source_repo = TaskSourceRepository(session)
            subject_repo = SubjectRepository(session)
            resource_repo = ResourceRepository(session)

            tasks = await task_repo.list_by_source(
                user_id=user_id, source=TaskSource.GOOGLE_CALENDAR
            )
            task_by_id = {task.id: task for task in tasks}

            event_to_task: dict[str, Task] = {}
            mappings = await source_repo.list_by_source_for_user(
                user_id, TaskSource.GOOGLE_CALENDAR.value
            )
            for mapping in mappings:
                task = task_by_id.get(mapping.task_id)
                if task is not None:
                    event_to_task[mapping.source_event_id] = task

            fp_index: dict[tuple, Task] = {}
            for task in tasks:
                fp = fingerprint(
                    title=task.title,
                    due_at=task.due_at,
                    timezone=task.timezone,
                    subject=task.subject.name if task.subject else None,
                )
                fp_index.setdefault(fp, task)

            seen_event_ids: set[str] = set()
            for raw in raw_events:
                event = normalize_event(raw, self._timezone)
                if not event.event_id or not is_task_event(event.title):
                    result.skipped += 1
                    continue
                seen_event_ids.add(event.event_id)
                await self._upsert_event(
                    session=session,
                    user_id=user_id,
                    event=event,
                    now=now,
                    task_repo=task_repo,
                    source_repo=source_repo,
                    subject_repo=subject_repo,
                    resource_repo=resource_repo,
                    event_to_task=event_to_task,
                    fp_index=fp_index,
                    result=result,
                )

            await self._mark_removed(
                session=session,
                tasks=tasks,
                seen_event_ids=seen_event_ids,
                now=now,
                task_repo=task_repo,
                result=result,
            )

        return result

    async def _upsert_event(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        event: NormalizedEvent,
        now: datetime,
        task_repo: TaskRepository,
        source_repo: TaskSourceRepository,
        subject_repo: SubjectRepository,
        resource_repo: ResourceRepository,
        event_to_task: dict[str, Task],
        fp_index: dict[tuple, Task],
        result: SyncResult,
    ) -> None:
        source = TaskSource.GOOGLE_CALENDAR
        task = event_to_task.get(event.event_id)

        if task is None:
            # ¿Evento nuevo, o duplicado de una tarea existente?
            fp = fingerprint(
                title=event.title,
                due_at=event.due_at,
                timezone=event.timezone,
                subject=event.subject,
            )
            candidate = fp_index.get(fp)
            if candidate is not None:
                await source_repo.add(
                    task_id=candidate.id,
                    source=source.value,
                    source_event_id=event.event_id,
                    is_primary=False,
                )
                await task_repo.add_history(
                    candidate,
                    HistoryEventType.DUPLICADO_CONSOLIDADO,
                    details={
                        "consolidated_event_id": event.event_id,
                        "reason": "mismo título, fecha y materia",
                    },
                )
                event_to_task[event.event_id] = candidate
                candidate.last_seen_at = now
                result.consolidated += 1
                return

            subject = await self._resolve_subject(session, user_id, subject_repo, event.subject)
            task = await task_repo.create(
                user_id=user_id,
                title=event.title,
                subject_id=subject.id if subject else None,
                description=event.description,
                instructions=event.instructions,
                due_at=event.due_at,
                timezone=event.timezone,
                source=source,
                source_event_id=event.event_id,
            )
            await source_repo.add(
                task_id=task.id,
                source=source.value,
                source_event_id=event.event_id,
                is_primary=True,
            )
            await task_repo.add_history(task, HistoryEventType.CREADA, details={"event_id": event.event_id})
            await self._add_resources(resource_repo, task, event)
            task.last_seen_at = now
            event_to_task[event.event_id] = task
            fp_index.setdefault(
                fingerprint(
                    title=task.title,
                    due_at=task.due_at,
                    timezone=task.timezone,
                    subject=subject.name if subject else None,
                ),
                task,
            )
            result.created += 1
            return

        # --- Evento ya mapeado: detectar cambios ---
        task.last_seen_at = now
        if task.removed_from_source_at is not None:
            task.removed_from_source_at = None
            await task_repo.add_history(
                task, HistoryEventType.ACTUALIZADA, details={"event_id": event.event_id, "reason": "evento reapareció"}
            )

        changed = await self._apply_changes(
            session=session,
            user_id=user_id,
            task=task,
            event=event,
            task_repo=task_repo,
            subject_repo=subject_repo,
            resource_repo=resource_repo,
        )
        if changed:
            result.updated += 1
        else:
            result.unchanged += 1

    async def _apply_changes(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        task: Task,
        event: NormalizedEvent,
        task_repo: TaskRepository,
        subject_repo: SubjectRepository,
        resource_repo: ResourceRepository,
    ) -> bool:
        changed = False

        if task.title != event.title:
            old = task.title
            task.title = event.title
            await task_repo.add_history(
                task, HistoryEventType.ACTUALIZADA,
                from_value=old, to_value=event.title,
                details={"field": "title", "event_id": event.event_id},
            )
            changed = True

        if task.description != event.description:
            task.description = event.description
            await task_repo.add_history(
                task, HistoryEventType.ACTUALIZADA,
                details={"field": "description", "event_id": event.event_id},
            )
            changed = True

        if task.due_at != event.due_at:
            old_due = task.due_at.isoformat() if task.due_at else None
            new_due = event.due_at.isoformat() if event.due_at else None
            task.due_at = event.due_at
            task.timezone = event.timezone
            await task_repo.add_history(
                task, HistoryEventType.FECHA_CAMBIADA,
                from_value=old_due, to_value=new_due,
                details={"event_id": event.event_id},
            )
            changed = True

        subject = await self._resolve_subject(session, user_id, subject_repo, event.subject)
        new_subject_id = subject.id if subject else None
        if task.subject_id != new_subject_id:
            task.subject_id = new_subject_id
            await task_repo.add_history(
                task, HistoryEventType.ACTUALIZADA,
                details={"field": "subject", "event_id": event.event_id},
            )
            changed = True

        if await self._add_resources(resource_repo, task, event):
            changed = True

        return changed

    async def _add_resources(
        self, resource_repo: ResourceRepository, task: Task, event: NormalizedEvent
    ) -> bool:
        added = False
        for resource in event.resources:
            if not resource.uri:
                continue
            existing = await resource_repo.get_by_uri(task.id, resource.uri)
            if existing is None:
                await resource_repo.add(
                    task_id=task.id,
                    resource_type=_to_resource_type(resource.resource_type),
                    name=resource.name,
                    uri=resource.uri,
                )
                added = True
        return added

    async def _resolve_subject(
        self,
        session: AsyncSession,
        user_id: int,
        subject_repo: SubjectRepository,
        name: str | None,
    ):
        if not name:
            return None
        subject = await subject_repo.get_by_name_ci(user_id=user_id, name=name)
        if subject is not None:
            return subject
        try:
            return await subject_repo.create(user_id=user_id, name=name)
        except IntegrityError:
            await session.rollback()
            subject = await subject_repo.get_by_name_ci(user_id=user_id, name=name)
            if subject is None:
                raise
            return subject

    async def _mark_removed(
        self,
        *,
        session: AsyncSession,
        tasks: list[Task],
        seen_event_ids: set[str],
        now: datetime,
        task_repo: TaskRepository,
        result: SyncResult,
    ) -> None:
        for task in tasks:
            if not task.source_event_id:
                continue
            if task.source_event_id in seen_event_ids:
                continue
            if task.removed_from_source_at is not None:
                continue
            task.removed_from_source_at = now
            await task_repo.add_history(
                task,
                HistoryEventType.REMOVIDA_DE_FUENTE,
                details={"event_id": task.source_event_id},
            )
            result.removed += 1

    async def _acquire_lock(self, session: AsyncSession, user_id: int) -> None:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:ns, :key)"),
            {"ns": _SYNC_LOCK_NAMESPACE, "key": user_id},
        )


def _to_resource_type(resource_type: str) -> ResourceType:
    try:
        return ResourceType(resource_type)
    except ValueError:
        return ResourceType.OTRO
