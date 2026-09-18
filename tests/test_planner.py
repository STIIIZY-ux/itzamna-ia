"""Tests del planner determinista (puro, sin base de datos)."""

from datetime import datetime, timedelta, timezone

from app.domain.enums import RiskLevel, TaskPriority, TaskStatus
from app.planner.engine import (
    FALLBACK_ESTIMATE_MINUTES,
    compute_score,
    first_step,
    is_actionable,
    next_task,
    suggest_start_time,
    urgency_label,
)
from app.planner.models import PlannerTask
from app.planner.risk import assess_risk

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


def _task(
    task_id: int,
    *,
    due_delta_minutes: int | None = 0,
    priority: TaskPriority = TaskPriority.MEDIA,
    estimated: int | None = 60,
    status: TaskStatus = TaskStatus.PENDIENTE,
    instructions: str | None = None,
) -> PlannerTask:
    due = NOW + timedelta(minutes=due_delta_minutes) if due_delta_minutes is not None else None
    return PlannerTask(
        id=task_id,
        title=f"Tarea {task_id}",
        subject=None,
        due_at=due,
        timezone="America/Tijuana",
        priority=priority,
        estimated_minutes=estimated,
        status=status,
        instructions=instructions,
    )


def test_is_actionable() -> None:
    assert is_actionable(_task(1)) is True
    assert is_actionable(_task(1, status=TaskStatus.TERMINADA)) is False
    assert is_actionable(_task(1, status=TaskStatus.ENTREGADA)) is False


def test_overdue_scores_higher_than_future() -> None:
    overdue = compute_score(_task(1, due_delta_minutes=-60), NOW)
    future = compute_score(_task(2, due_delta_minutes=60 * 24 * 7), NOW)
    assert overdue > future


def test_higher_priority_scores_higher() -> None:
    urgent = compute_score(_task(1, priority=TaskPriority.URGENTE, due_delta_minutes=60 * 24), NOW)
    low = compute_score(_task(2, priority=TaskPriority.BAJA, due_delta_minutes=60 * 24), NOW)
    assert urgent > low


def test_closer_deadline_scores_higher() -> None:
    soon = compute_score(_task(1, due_delta_minutes=60), NOW)
    later = compute_score(_task(2, due_delta_minutes=60 * 24 * 7), NOW)
    assert soon > later


def test_missing_estimate_uses_fallback() -> None:
    no_estimate = compute_score(_task(1, estimated=None), NOW)
    with_fallback = compute_score(_task(2, estimated=FALLBACK_ESTIMATE_MINUTES), NOW)
    assert no_estimate == with_fallback


def test_next_task_returns_best_single() -> None:
    tasks = [
        _task(1, due_delta_minutes=60 * 24 * 7),
        _task(2, due_delta_minutes=-30),
    ]
    recommendation = next_task(tasks, NOW)
    assert recommendation is not None
    assert recommendation.task.id == 2


def test_next_task_empty() -> None:
    assert next_task([], NOW) is None


def test_suggest_start_before_due() -> None:
    # due in 120 min, estimate 30 + buffer 30 => start ~60 min before due
    task = _task(1, due_delta_minutes=120, estimated=30)
    start = suggest_start_time(task, NOW)
    assert start is not None
    assert (task.due_at - start).total_seconds() == 60 * 60


def test_suggest_start_past_returns_now() -> None:
    task = _task(1, due_delta_minutes=10)
    assert suggest_start_time(task, NOW) == NOW


def test_suggest_start_no_due_returns_none() -> None:
    task = _task(1, due_delta_minutes=None)
    assert suggest_start_time(task, NOW) is None


def test_first_step_uses_instructions() -> None:
    assert first_step(_task(1, instructions="Hacer 1-10")) == "Revisar las instrucciones"
    assert first_step(_task(1)) == "Definir el primer paso"


def test_urgency_labels() -> None:
    assert urgency_label(_task(1, due_delta_minutes=-10), NOW) == "ya venció"
    assert urgency_label(_task(1, due_delta_minutes=30), NOW) == "sin margen"
    assert urgency_label(_task(1, due_delta_minutes=60 * 5), NOW) == "vence hoy"
    assert urgency_label(_task(1, due_delta_minutes=60 * 48), NOW) == "vence pronto"
    assert urgency_label(_task(1, due_delta_minutes=60 * 24 * 7), NOW) == "con tiempo"
    assert urgency_label(_task(1, due_delta_minutes=None), NOW) == "sin fecha"


def test_risk_critico_overdue() -> None:
    assert assess_risk(_task(1, due_delta_minutes=-1), NOW) is RiskLevel.CRITICO


def test_risk_critico_high_priority_no_start() -> None:
    task = _task(1, priority=TaskPriority.ALTA, due_delta_minutes=60 * 5, status=TaskStatus.PENDIENTE)
    assert assess_risk(task, NOW) is RiskLevel.CRITICO


def test_risk_riesgo_close_deadline() -> None:
    assert assess_risk(_task(1, due_delta_minutes=60 * 10), NOW) is RiskLevel.RIESGO


def test_risk_atencion() -> None:
    assert assess_risk(_task(1, due_delta_minutes=60 * 48), NOW) is RiskLevel.ATENCION


def test_risk_normal() -> None:
    assert assess_risk(_task(1, due_delta_minutes=60 * 24 * 7), NOW) is RiskLevel.NORMAL


def test_risk_broken_commitment_is_riesgo() -> None:
    task = _task(1, due_delta_minutes=60 * 24 * 7)
    assert assess_risk(task, NOW, has_broken_commitment=True) is RiskLevel.RIESGO
