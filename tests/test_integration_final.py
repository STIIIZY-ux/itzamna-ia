"""Tests del Academic Score, estadísticas, briefing, procrastinación y rescate."""

from app.services.briefing import BriefingService
from app.services.procrastination import ProcrastinationService
from app.services.rescue import RescueService
from app.services.score import AcademicScoreService
from app.services.statistics import StatisticsService


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=2000)
    return user.id


async def test_academic_score_empty_user(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    result = await AcademicScoreService(session_factory).compute(user_id)
    # Sin datos, la puntuación es 100 (denominadores 0 -> fracción 1.0).
    assert 0 <= result.score <= 100
    assert set(result.breakdown) == {"puntualidad", "completitud", "dominio", "quizzes", "constancia"}


async def test_academic_score_with_completed_task(
    session, session_factory, user_service, task_service
) -> None:
    user_id = await _make_user(user_service)
    await task_service.create_task(user_id=user_id, title="T")
    result = await AcademicScoreService(session_factory).compute(user_id)
    assert result.score < 100  # hay tarea pendiente -> completitud < 1


async def test_statistics_totals(session, session_factory, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    await task_service.create_task(user_id=user_id, title="Pendiente")
    stats = await StatisticsService(session_factory).totals(user_id)
    assert stats.tasks_total == 1
    assert stats.tasks_completed == 0


async def test_procrastination_normal(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    report = await ProcrastinationService(session_factory).detect(user_id)
    assert report.level.value == "normal"
    assert report.reasons == []


async def test_rescue_no_candidates(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    offer = await RescueService(session_factory).offer(user_id)
    assert offer is None


async def test_briefing_daily(session, session_factory, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    await task_service.create_task(user_id=user_id, title="Tarea de hoy")
    text = await BriefingService(session_factory, None, "America/Tijuana").daily_briefing(user_id)
    assert "Resumen del día" in text


async def test_briefing_weekly_deterministic(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    text = await BriefingService(session_factory, None, "America/Tijuana").weekly_audit(user_id)
    assert "Auditoría semanal" in text
