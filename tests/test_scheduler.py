"""Tests del scheduler persistente."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.db.models import ScheduledJob
from app.domain.enums import JobKind, JobStatus
from app.scheduler.dispatch import make_dispatcher
from app.scheduler.runner import SchedulerRunner
from app.scheduler.service import SchedulerService


@pytest.fixture
def scheduler(session_factory):
    return SchedulerService(session_factory)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=700)
    return user.id


class FakeDispatcher:
    def __init__(self) -> None:
        self.jobs: list[ScheduledJob] = []

    async def __call__(self, job: ScheduledJob) -> bool:
        self.jobs.append(job)
        return True


async def test_schedule_idempotent(session, scheduler, user_service) -> None:
    user_id = await _make_user(user_service)
    at = _now() + timedelta(minutes=5)
    first = await scheduler.schedule(
        user_id=user_id, kind=JobKind.NUDGE, scheduled_at=at, dedup_key="nudge:1:1"
    )
    second = await scheduler.schedule(
        user_id=user_id, kind=JobKind.NUDGE, scheduled_at=at, dedup_key="nudge:1:1"
    )
    assert first is not None
    assert second is None


async def test_claim_due_only_claims_due(session, scheduler, user_service) -> None:
    user_id = await _make_user(user_service)
    await scheduler.schedule(
        user_id=user_id, kind=JobKind.NUDGE, scheduled_at=_now() - timedelta(minutes=1), dedup_key="a"
    )
    await scheduler.schedule(
        user_id=user_id, kind=JobKind.NUDGE, scheduled_at=_now() + timedelta(hours=1), dedup_key="b"
    )
    jobs = await scheduler.claim_due(now=_now(), limit=10)
    assert len(jobs) == 1
    assert jobs[0].dedup_key == "a"
    assert jobs[0].status is JobStatus.CLAIMED


async def test_concurrent_claim_no_double(session, scheduler, user_service) -> None:
    user_id = await _make_user(user_service)
    due = _now() - timedelta(minutes=1)
    await scheduler.schedule(user_id=user_id, kind=JobKind.NUDGE, scheduled_at=due, dedup_key="a")
    await scheduler.schedule(user_id=user_id, kind=JobKind.NUDGE, scheduled_at=due, dedup_key="b")

    first = await scheduler.claim_due(now=_now(), limit=10)
    second = await scheduler.claim_due(now=_now(), limit=10)

    assert len(first) == 2
    assert len(second) == 0


async def test_runner_tick_dispatches_due(session, session_factory, scheduler, user_service) -> None:
    user_id = await _make_user(user_service)
    await scheduler.schedule(
        user_id=user_id, kind=JobKind.NUDGE, scheduled_at=_now() - timedelta(minutes=1), dedup_key="n"
    )
    dispatcher = FakeDispatcher()
    runner = SchedulerRunner(
        scheduler=scheduler,
        dispatch=dispatcher,
        poll_interval_seconds=999,
        stale_claim_seconds=300,
        claim_batch_size=10,
    )
    dispatched = await runner.tick()
    assert dispatched == 1
    assert len(dispatcher.jobs) == 1


async def test_recover_stale_claims(session, session_factory, scheduler, user_service) -> None:
    user_id = await _make_user(user_service)
    await scheduler.schedule(
        user_id=user_id, kind=JobKind.NUDGE, scheduled_at=_now() - timedelta(minutes=1), dedup_key="x"
    )
    jobs = await scheduler.claim_due(now=_now(), limit=10)
    assert len(jobs) == 1

    # Simula un worker caído: marca el claim como muy viejo.
    async with session_factory() as s:
        await s.execute(
            update(ScheduledJob)
            .where(ScheduledJob.id == jobs[0].id)
            .values(claimed_at=_now() - timedelta(minutes=60))
        )
        await s.commit()

    recovered = await scheduler.recover_stale(stale_before=_now() - timedelta(minutes=10))
    assert recovered == 1

    reclaimed = await scheduler.claim_due(now=_now(), limit=10)
    assert len(reclaimed) == 1


async def test_make_dispatcher_sends_message(
    session, session_factory, user_service, task_service
) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="Entregar práctica")
    sent: list[tuple[int, str]] = []

    async def send(chat_id: int, text: str) -> None:
        sent.append((chat_id, text))

    dispatch = make_dispatcher(send, session_factory, "America/Tijuana")
    job = ScheduledJob(user_id=user_id, task_id=task.id, kind=JobKind.START_REMINDER)
    ok = await dispatch(job)

    assert ok is True
    assert len(sent) == 1
    assert "Entregar práctica" in sent[0][1]
