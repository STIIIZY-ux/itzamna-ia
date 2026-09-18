"""Tests del modo emergencia."""

from datetime import datetime, timedelta, timezone

from app.domain.enums import TaskPriority
from app.services.emergency import EmergencyService
from tests.fake_ai import FakeAIService

TZ = "America/Tijuana"


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=1200)
    return user.id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def test_assess_no_tasks(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    assessment = await EmergencyService(session_factory, None).assess(user_id)
    assert assessment.task_id is None


async def test_assess_critical_task_missing_instructions(
    session, session_factory, user_service, task_service
) -> None:
    user_id = await _make_user(user_service)
    await task_service.create_task(
        user_id=user_id,
        title="Entrega urgente",
        priority=TaskPriority.URGENTE,
        due_at=_now() + timedelta(hours=2),
    )
    assessment = await EmergencyService(session_factory, None).assess(user_id)
    assert assessment.task_id is not None
    assert assessment.risk is not None
    assert "instrucciones" in assessment.missing
    assert assessment.time_remaining is not None


async def test_build_plan_deterministic(
    session, session_factory, user_service, task_service
) -> None:
    user_id = await _make_user(user_service)
    await task_service.create_task(
        user_id=user_id,
        title="Entrega urgente",
        priority=TaskPriority.URGENTE,
        due_at=_now() + timedelta(hours=2),
    )
    plan = await EmergencyService(session_factory, None).build_plan(user_id)
    assert "FASE 1" in plan
    assert "FASE 6" in plan
    assert "Necesito lo siguiente" in plan


async def test_build_plan_no_tasks(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    plan = await EmergencyService(session_factory, None).build_plan(user_id)
    assert "No hay ninguna actividad en estado crítico" in plan


async def test_build_plan_with_ai(
    session, session_factory, user_service, task_service
) -> None:
    user_id = await _make_user(user_service)
    await task_service.create_task(
        user_id=user_id,
        title="Proyecto",
        priority=TaskPriority.ALTA,
        due_at=_now() + timedelta(hours=5),
        instructions="Hacer un informe",
    )
    ai = FakeAIService(["Plan generado por IA en fases."])
    plan = await EmergencyService(session_factory, ai).build_plan(user_id)
    assert "Plan generado por IA" in plan


async def test_build_plan_ai_failure_falls_back(
    session, session_factory, user_service, task_service
) -> None:
    from app.ai.errors import AIProviderError

    class FailingAI(FakeAIService):
        async def complete(self, messages, **kwargs):
            raise AIProviderError("caído")

    user_id = await _make_user(user_service)
    await task_service.create_task(
        user_id=user_id,
        title="Proyecto",
        priority=TaskPriority.ALTA,
        due_at=_now() + timedelta(hours=5),
    )
    plan = await EmergencyService(session_factory, FailingAI()).build_plan(user_id)
    assert "FASE 1" in plan  # fallback determinista
