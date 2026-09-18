"""Tests de integración de la sincronización Google Calendar -> tareas."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Task, TaskEventSource
from app.domain.enums import HistoryEventType, TaskSource
from app.repositories.tasks import TaskRepository
from app.services.calendar_sync import CalendarSyncService

TZ = "America/Tijuana"


class FakeCalendarClient:
    def __init__(self, events: list[dict]) -> None:
        self._events = events

    async def list_events(self, *, user_id, calendar_id, time_min, time_max):
        return list(self._events)


def _event(event_id: str, summary: str, date: str, description: str | None = None) -> dict:
    return {
        "id": event_id,
        "summary": summary,
        "start": {"date": date},
        "description": description,
    }


def _service(session_factory, events: list[dict]) -> CalendarSyncService:
    return CalendarSyncService(
        session_factory=session_factory,
        client=FakeCalendarClient(events),
        timezone=TZ,
        calendar_id="primary",
        time_window_days=30,
    )


async def _user_id(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=500)
    return user.id


async def _tasks(session, user_id: int) -> list[Task]:
    result = await session.execute(
        select(Task).options(selectinload(Task.subject)).where(Task.user_id == user_id)
    )
    return list(result.scalars().all())


async def _task_with_history(session, user_id: int, task_id: int) -> Task:
    return await TaskRepository(session).get(user_id=user_id, task_id=task_id)


async def test_new_event_creates_task(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    result = await _service(session_factory, [_event("e1", "Entrega 1", "2026-09-04")]).sync(user_id)

    assert result.created == 1
    tasks = await _tasks(session, user_id)
    assert len(tasks) == 1
    assert tasks[0].source == TaskSource.GOOGLE_CALENDAR
    assert tasks[0].source_event_id == "e1"
    assert tasks[0].due_at.date().isoformat() == "2026-09-04"


async def test_sync_is_idempotent(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    events = [_event("e1", "Entrega 1", "2026-09-04")]
    service = _service(session_factory, events)

    first = await service.sync(user_id)
    second = await service.sync(user_id)

    assert first.created == 1
    assert second.created == 0
    assert second.unchanged == 1
    assert len(await _tasks(session, user_id)) == 1


async def test_modified_event_updates_task(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    await _service(session_factory, [_event("e1", "Entrega 1", "2026-09-04")]).sync(user_id)

    result = await _service(session_factory, [_event("e1", "Entrega 1", "2026-09-06")]).sync(user_id)

    assert result.updated == 1
    tasks = await _tasks(session, user_id)
    assert tasks[0].due_at.date().isoformat() == "2026-09-06"
    task = await _task_with_history(session, user_id, tasks[0].id)
    assert HistoryEventType.FECHA_CAMBIADA in [h.event_type for h in task.history]


async def test_deleted_event_marks_removed(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    await _service(session_factory, [_event("e1", "Entrega 1", "2026-09-04")]).sync(user_id)

    result = await _service(session_factory, []).sync(user_id)

    assert result.removed == 1
    tasks = await _tasks(session, user_id)
    assert tasks[0].removed_from_source_at is not None
    task = await _task_with_history(session, user_id, tasks[0].id)
    assert HistoryEventType.REMOVIDA_DE_FUENTE in [h.event_type for h in task.history]


async def test_duplicate_events_consolidate(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    events = [
        _event("e1", "Actividad 3", "2026-09-04"),
        _event("e2", "Actividad 3", "2026-09-04"),
    ]
    result = await _service(session_factory, events).sync(user_id)

    assert result.created == 1
    assert result.consolidated == 1
    tasks = await _tasks(session, user_id)
    assert len(tasks) == 1

    mappings = (
        (await session.execute(select(TaskEventSource).where(TaskEventSource.task_id == tasks[0].id)))
        .scalars()
        .all()
    )
    assert {m.source_event_id for m in mappings} == {"e1", "e2"}
    task = await _task_with_history(session, user_id, tasks[0].id)
    assert HistoryEventType.DUPLICADO_CONSOLIDADO in [h.event_type for h in task.history]


async def test_ambiguous_events_kept_separate(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    events = [
        _event("e1", "Actividad 3", "2026-09-04"),
        _event("e2", "Actividad 3", "2026-09-05"),
    ]
    result = await _service(session_factory, events).sync(user_id)

    assert result.created == 2
    assert result.consolidated == 0
    assert len(await _tasks(session, user_id)) == 2


async def test_non_task_events_skipped(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    events = [_event("e1", "Clase de cálculo", "2026-09-04")]
    result = await _service(session_factory, events).sync(user_id)

    assert result.skipped == 1
    assert await _tasks(session, user_id) == []


async def test_subject_extracted_and_reused(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    events = [
        _event("e1", "[Cálculo] Entrega 1", "2026-09-04"),
        _event("e2", "[Cálculo] Tarea 2", "2026-09-10"),
    ]
    await _service(session_factory, events).sync(user_id)

    tasks = await _tasks(session, user_id)
    subjects = {t.subject.name for t in tasks if t.subject}
    assert subjects == {"Cálculo"}

    from sqlalchemy import select as _select

    from app.db.models import Subject

    subject_count = len(
        (await session.execute(_select(Subject).where(Subject.user_id == user_id))).scalars().all()
    )
    assert subject_count == 1


async def test_removed_event_reappears(session, session_factory, user_service) -> None:
    user_id = await _user_id(user_service)
    await _service(session_factory, [_event("e1", "Entrega 1", "2026-09-04")]).sync(user_id)
    await _service(session_factory, []).sync(user_id)

    await _service(session_factory, [_event("e1", "Entrega 1", "2026-09-04")]).sync(user_id)

    tasks = await _tasks(session, user_id)
    assert len(tasks) == 1
    assert tasks[0].removed_from_source_at is None
