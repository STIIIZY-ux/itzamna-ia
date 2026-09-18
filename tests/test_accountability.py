"""Tests del servicio de accountability."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.db.models import Commitment, ScheduledJob
from app.domain.enums import AccountabilityMode, AccountabilityState, CommitmentStatus
from app.services.accountability import AccountabilityService
from app.services.notification_preferences import NotificationPreferencesService

TZ = "America/Tijuana"


def _now_active() -> datetime:
    # 19:00 local (dentro del horario activo 9-21).
    return datetime(2026, 9, 4, 19, 0, tzinfo=ZoneInfo(TZ))


@pytest.fixture
def acc_service(session_factory):
    return AccountabilityService(session_factory, tryhard_interval_minutes=120, guerra_interval_minutes=30)


@pytest.fixture
def prefs_service(session_factory):
    return NotificationPreferencesService(session_factory)


async def _user_task(user_service, task_service):
    user = await user_service.get_or_create_by_telegram(telegram_id=800)
    task = await task_service.create_task(user_id=user.id, title="Tarea")
    return user.id, task.id


async def test_record_commitment_sets_state(session, acc_service, user_service, task_service) -> None:
    uid, tid = await _user_task(user_service, task_service)
    commitment = await acc_service.record_commitment(user_id=uid, task_id=tid)
    assert commitment.status is CommitmentStatus.ACTIVO
    state = await acc_service.get_state(user_id=uid, task_id=tid)
    assert state is not None
    assert state.state is AccountabilityState.COMMITTED


async def test_record_commitment_idempotent(session, acc_service, user_service, task_service) -> None:
    uid, tid = await _user_task(user_service, task_service)
    first = await acc_service.record_commitment(user_id=uid, task_id=tid)
    second = await acc_service.record_commitment(user_id=uid, task_id=tid)
    assert first.id == second.id

    active = (
        (await session.execute(
            select(Commitment).where(Commitment.task_id == tid, Commitment.status == CommitmentStatus.ACTIVO)
        ))
        .scalars()
        .all()
    )
    assert len(active) == 1


async def test_schedule_follow_up_creates_nudge(session, acc_service, user_service, task_service) -> None:
    uid, tid = await _user_task(user_service, task_service)
    ok = await acc_service.schedule_follow_up(user_id=uid, task_id=tid, now=_now_active(), timezone_name=TZ)
    assert ok is True

    jobs = (await session.execute(select(ScheduledJob).where(ScheduledJob.task_id == tid))).scalars().all()
    assert len(jobs) == 1
    state = await acc_service.get_state(user_id=uid, task_id=tid)
    assert state.state is AccountabilityState.AWAITING_COMMITMENT
    assert state.reminder_count == 1


async def test_schedule_follow_up_respects_silence(
    session, acc_service, prefs_service, user_service, task_service
) -> None:
    uid, tid = await _user_task(user_service, task_service)
    await prefs_service.set_mode(uid, AccountabilityMode.SILENCIO)
    ok = await acc_service.schedule_follow_up(user_id=uid, task_id=tid, now=_now_active(), timezone_name=TZ)
    assert ok is False


async def test_schedule_follow_up_respects_pause(
    session, acc_service, prefs_service, user_service, task_service
) -> None:
    uid, tid = await _user_task(user_service, task_service)
    now = _now_active()
    await prefs_service.pause(uid, minutes=30, now=now)
    ok = await acc_service.schedule_follow_up(user_id=uid, task_id=tid, now=now, timezone_name=TZ)
    assert ok is False


async def test_schedule_follow_up_skips_committed(
    session, acc_service, user_service, task_service
) -> None:
    uid, tid = await _user_task(user_service, task_service)
    await acc_service.record_commitment(user_id=uid, task_id=tid)
    ok = await acc_service.schedule_follow_up(user_id=uid, task_id=tid, now=_now_active(), timezone_name=TZ)
    assert ok is False


async def test_schedule_follow_up_respects_limit(
    session, acc_service, user_service, task_service
) -> None:
    uid, tid = await _user_task(user_service, task_service)
    now = _now_active()
    results = [
        await acc_service.schedule_follow_up(user_id=uid, task_id=tid, now=now, timezone_name=TZ)
        for _ in range(6)
    ]
    assert results == [True, True, True, True, True, False]


async def test_rescue_candidate_flag(session, acc_service, user_service, task_service) -> None:
    uid, tid = await _user_task(user_service, task_service)
    await acc_service.set_rescue_candidate(user_id=uid, task_id=tid, value=True)
    state = await acc_service.get_state(user_id=uid, task_id=tid)
    assert state is not None
    assert state.rescue_candidate is True


async def test_mark_completed_clears_rescue(session, acc_service, user_service, task_service) -> None:
    uid, tid = await _user_task(user_service, task_service)
    await acc_service.set_rescue_candidate(user_id=uid, task_id=tid, value=True)
    await acc_service.mark_completed(user_id=uid, task_id=tid)
    state = await acc_service.get_state(user_id=uid, task_id=tid)
    assert state is not None
    assert state.state is AccountabilityState.COMPLETED
    assert state.rescue_candidate is False
