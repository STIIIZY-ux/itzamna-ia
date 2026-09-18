"""Tests de estimaciones adaptativas."""

from datetime import datetime, timedelta, timezone

from app.db.models import Task, TaskHistory
from app.domain.enums import HistoryEventType, TaskStatus
from app.services.adaptive import (
    AdaptiveEstimatesService,
    actual_duration_minutes,
    correction_factor,
)

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _hist(events: list[tuple[str, datetime]]) -> list[TaskHistory]:
    return [
        TaskHistory(event_type=HistoryEventType.ESTADO_CAMBIADO, to_value=value, created_at=at)
        for value, at in events
    ]


def test_actual_duration_from_start_to_end() -> None:
    history = _hist(
        [("iniciada", BASE), ("terminada", BASE + timedelta(minutes=130))]
    )
    assert actual_duration_minutes(history, BASE) == 130


def test_actual_duration_no_end_returns_none() -> None:
    history = _hist([("iniciada", BASE)])
    assert actual_duration_minutes(history, BASE) is None


def test_actual_duration_uses_created_at_as_fallback() -> None:
    # Sin evento de inicio: se usa created_at.
    history = _hist([("terminada", BASE + timedelta(minutes=60))])
    assert actual_duration_minutes(history, BASE) == 60


def test_correction_factor_needs_samples() -> None:
    assert correction_factor([]) is None
    assert correction_factor([(60, 60)]) is None  # una sola muestra


def test_correction_factor_average() -> None:
    factor = correction_factor([(60, 60), (60, 120)])
    assert factor == 1.5


def test_correction_factor_clamped() -> None:
    assert correction_factor([(60, 600), (60, 600)]) == 3.0
    assert correction_factor([(60, 10), (60, 10)]) == 0.5


async def test_recompute_sets_adjusted_estimate(session_factory, user_service, task_service) -> None:
    user = await user_service.get_or_create_by_telegram(telegram_id=1900)
    # Tareas completadas con duración real de 130 min vs estimación de 60.
    for _ in range(2):
        task = await task_service.create_task(
            user_id=user.id, title="Completada", estimated_minutes=60
        )
        async with session_factory() as s:
            t = await s.get(Task, task.id)
            t.status = TaskStatus.TERMINADA
            s.add_all(
                [
                    TaskHistory(
                        task_id=task.id,
                        event_type=HistoryEventType.ESTADO_CAMBIADO,
                        to_value="iniciada",
                        created_at=BASE,
                    ),
                    TaskHistory(
                        task_id=task.id,
                        event_type=HistoryEventType.ESTADO_CAMBIADO,
                        to_value="terminada",
                        created_at=BASE + timedelta(minutes=130),
                    ),
                ]
            )
            await s.commit()

    pending = await task_service.create_task(
        user_id=user.id, title="Pendiente", estimated_minutes=60
    )

    updated = await AdaptiveEstimatesService(session_factory).recompute(user_id=user.id)
    assert updated >= 1

    fetched = await task_service.get_task(user_id=user.id, task_id=pending.id)
    assert fetched.adjusted_estimated_minutes is not None
    assert fetched.adjusted_estimated_minutes > 60
    assert fetched.estimate_basis is not None
