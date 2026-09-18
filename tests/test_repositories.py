"""Tests de repositorios."""

from app.domain.enums import HistoryEventType, TaskPriority, TaskStatus
from app.repositories.commitments import CommitmentRepository
from app.repositories.subjects import SubjectRepository
from app.repositories.tasks import TaskRepository
from app.repositories.users import UserRepository


async def test_user_get_or_create_idempotent(session) -> None:
    repo = UserRepository(session)
    u1 = await repo.get_or_create(telegram_id=111, username="a", first_name="A")
    await session.commit()
    u2 = await repo.get_or_create(telegram_id=111, username="b")
    assert u1.id == u2.id


async def test_user_get_by_telegram_id_missing(session) -> None:
    repo = UserRepository(session)
    assert await repo.get_by_telegram_id(999) is None


async def test_subject_repository_crud(session) -> None:
    user_repo = UserRepository(session)
    user = await user_repo.get_or_create(telegram_id=222)
    await session.flush()

    repo = SubjectRepository(session)
    subject = await repo.create(user_id=user.id, name="Álgebra")
    await session.commit()

    assert await repo.get(user_id=user.id, subject_id=subject.id) is not None
    assert await repo.get_by_name(user_id=user.id, name="Álgebra") is not None
    assert (await repo.list_subjects(user_id=user.id))[0].name == "Álgebra"
    assert await repo.delete(user_id=user.id, subject_id=subject.id) is True
    assert await repo.delete(user_id=user.id, subject_id=subject.id) is False


async def test_subject_scoped_to_user(session) -> None:
    user_repo = UserRepository(session)
    user_a = await user_repo.get_or_create(telegram_id=1)
    user_b = await user_repo.get_or_create(telegram_id=2)
    await session.flush()

    repo = SubjectRepository(session)
    subject = await repo.create(user_id=user_a.id, name="Historia")
    await session.commit()

    assert await repo.get(user_id=user_b.id, subject_id=subject.id) is None


async def test_task_repository_crud_and_filters(session) -> None:
    user_repo = UserRepository(session)
    user = await user_repo.get_or_create(telegram_id=333)
    await session.flush()

    repo = TaskRepository(session)
    task = await repo.create(user_id=user.id, title="Leer capítulo 1", priority=TaskPriority.ALTA)
    await session.commit()

    fetched = await repo.get(user_id=user.id, task_id=task.id)
    assert fetched is not None
    assert fetched.status is TaskStatus.PENDIENTE

    listed = await repo.list_tasks(user_id=user.id, status=TaskStatus.PENDIENTE)
    assert len(listed) == 1
    assert await repo.list_tasks(user_id=user.id, status=TaskStatus.TERMINADA) == []

    assert await repo.delete(user_id=user.id, task_id=task.id) is True
    assert await repo.delete(user_id=user.id, task_id=task.id) is False


async def test_task_add_history(session) -> None:
    from sqlalchemy import select

    from app.db.models import TaskHistory

    user_repo = UserRepository(session)
    user = await user_repo.get_or_create(telegram_id=444)
    await session.flush()
    repo = TaskRepository(session)
    task = await repo.create(user_id=user.id, title="T")
    await repo.add_history(task, HistoryEventType.CREADA)
    await session.commit()

    entries = (
        (await session.execute(select(TaskHistory).where(TaskHistory.task_id == task.id)))
        .scalars()
        .all()
    )
    assert len(entries) == 1
    assert entries[0].event_type is HistoryEventType.CREADA


async def test_commitment_repository(session) -> None:
    user_repo = UserRepository(session)
    user = await user_repo.get_or_create(telegram_id=555)
    await session.flush()
    task = await TaskRepository(session).create(user_id=user.id, title="T")
    await session.flush()

    repo = CommitmentRepository(session)
    commitment = await repo.create(task_id=task.id, user_id=user.id)
    await session.commit()

    assert await repo.get(user_id=user.id, commitment_id=commitment.id) is not None
    assert len(await repo.list_for_task(user_id=user.id, task_id=task.id)) == 1
