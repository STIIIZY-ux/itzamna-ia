"""Tests de modelos ORM: relaciones, cascada y persistencia de enums."""

from sqlalchemy import select

from app.db.models import Subject, Task, TaskHistory, User
from app.domain.enums import HistoryEventType, TaskPriority, TaskSource, TaskStatus


async def test_user_subject_task_relationship(session) -> None:
    user = User(telegram_id=111, username="alumno")
    subject = Subject(user=user, name="Cálculo")
    task = Task(
        user=user,
        subject=subject,
        title="Tarea 1",
        source=TaskSource.MANUAL,
        priority=TaskPriority.ALTA,
        status=TaskStatus.PENDIENTE,
    )
    session.add_all([user, subject, task])
    await session.flush()

    assert task.subject is subject
    assert task in user.tasks
    assert task in subject.tasks


async def test_task_enum_roundtrip(session) -> None:
    user = User(telegram_id=222)
    session.add(user)
    await session.flush()

    task = Task(
        user_id=user.id,
        title="T",
        source=TaskSource.GOOGLE_CALENDAR,
        source_event_id="evt-123",
        priority=TaskPriority.URGENTE,
        status=TaskStatus.EN_PROGRESO,
    )
    session.add(task)
    await session.commit()

    fetched = (
        await session.execute(select(Task).where(Task.id == task.id))
    ).scalar_one()
    assert fetched.source is TaskSource.GOOGLE_CALENDAR
    assert fetched.source_event_id == "evt-123"
    assert fetched.priority is TaskPriority.URGENTE
    assert fetched.status is TaskStatus.EN_PROGRESO


async def test_history_jsonb_details(session) -> None:
    user = User(telegram_id=333)
    task = Task(user=user, title="T")
    session.add_all([user, task])
    await session.flush()

    entry = TaskHistory(
        task_id=task.id,
        event_type=HistoryEventType.ESTADO_CAMBIADO,
        from_value="pendiente",
        to_value="iniciada",
        details={"reason": "empezó", "score": 5},
    )
    session.add(entry)
    await session.commit()

    fetched = (
        await session.execute(select(TaskHistory).where(TaskHistory.id == entry.id))
    ).scalar_one()
    assert fetched.details == {"reason": "empezó", "score": 5}


async def test_cascade_delete_user_removes_tasks(session) -> None:
    user = User(telegram_id=444)
    task = Task(user=user, title="T")
    session.add_all([user, task])
    await session.commit()

    await session.delete(user)
    await session.commit()

    remaining = (await session.execute(select(Task))).scalars().all()
    assert remaining == []


async def test_subject_delete_sets_task_subject_null(session) -> None:
    user = User(telegram_id=555)
    subject = Subject(user=user, name="Física")
    task = Task(user=user, subject=subject, title="T")
    session.add_all([user, subject, task])
    await session.commit()

    await session.delete(subject)
    await session.commit()

    fetched = (await session.execute(select(Task))).scalar_one()
    assert fetched.subject_id is None


async def test_duplicate_subject_per_user_rejected(session) -> None:
    user = User(telegram_id=666)
    session.add(user)
    await session.flush()
    session.add(Subject(user_id=user.id, name="Química"))
    await session.commit()

    session.add(Subject(user_id=user.id, name="Química"))
    from sqlalchemy.exc import IntegrityError

    try:
        await session.commit()
        assert False, "se esperaba IntegrityError"
    except IntegrityError:
        await session.rollback()
