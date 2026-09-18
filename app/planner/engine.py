"""Motor determinista del planner.

El criterio de ordenación es deliberadamente simple y explicable:

    score = peso_prioridad * 1000 + urgencia

donde ``urgencia`` es una clasificación por bandas de tiempo restante frente al
esfuerzo estimado. No usa IA.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.enums import TaskPriority, TaskStatus

from .models import PlannerTask, TaskRecommendation

PRIORITY_WEIGHTS: dict[TaskPriority, int] = {
    TaskPriority.BAJA: 1,
    TaskPriority.MEDIA: 2,
    TaskPriority.ALTA: 3,
    TaskPriority.URGENTE: 4,
}

#: Estimación por defecto cuando la tarea no tiene ``estimated_minutes``.
#: Es un fallback explícito, NO una estimación aprendida.
FALLBACK_ESTIMATE_MINUTES = 60

#: Margen de seguridad para terminar antes de la entrega.
START_BUFFER_MINUTES = 30

_TERMINAL_STATES = {TaskStatus.TERMINADA, TaskStatus.ENTREGADA}

_URGENCY_TIERS = (
    (0, "ya venció"),
    (60 * 24, "vence hoy"),
    (72 * 60, "vence pronto"),
)


def is_actionable(task: PlannerTask) -> bool:
    """Indica si la tarea es candidata a trabajarse ahora."""
    return task.status not in _TERMINAL_STATES


def _effort(task: PlannerTask) -> int:
    if task.adjusted_estimated_minutes is not None:
        return task.adjusted_estimated_minutes
    if task.estimated_minutes is not None:
        return task.estimated_minutes
    return FALLBACK_ESTIMATE_MINUTES


def urgency_label(task: PlannerTask, now: datetime) -> str:
    """Etiqueta humana de urgencia."""
    if task.due_at is None:
        return "sin fecha"
    minutes_left = (task.due_at - now).total_seconds() / 60
    effort = _effort(task)
    if minutes_left <= 0:
        return "ya venció"
    if minutes_left <= effort:
        return "sin margen"
    if minutes_left <= 60 * 24:
        return "vence hoy"
    if minutes_left <= 72 * 60:
        return "vence pronto"
    return "con tiempo"


def _urgency_score(task: PlannerTask, now: datetime) -> int:
    if task.due_at is None:
        return 0
    minutes_left = (task.due_at - now).total_seconds() / 60
    effort = _effort(task)
    if minutes_left <= 0:
        return 100_000
    if minutes_left <= effort:
        return 10_000
    if minutes_left <= 60 * 24:
        return 1_000
    if minutes_left <= 72 * 60:
        return 100
    return 10


def compute_score(task: PlannerTask, now: datetime) -> float:
    """Puntuación determinista: mayor = trabajar antes."""
    return PRIORITY_WEIGHTS[task.priority] * 1000 + _urgency_score(task, now)


def suggest_start_time(task: PlannerTask, now: datetime) -> datetime | None:
    """Sugiere cuándo comenzar para terminar antes de la entrega."""
    if task.due_at is None:
        return None
    start = task.due_at - timedelta(minutes=_effort(task) + START_BUFFER_MINUTES)
    return max(now, start)


def first_step(task: PlannerTask) -> str:
    """Primera acción concreta sugerida."""
    if task.instructions:
        return "Revisar las instrucciones"
    if task.subject:
        return "Revisar el material de la materia"
    return "Definir el primer paso"


def build_recommendation(task: PlannerTask, now: datetime) -> TaskRecommendation:
    return TaskRecommendation(
        task=task,
        score=compute_score(task, now),
        urgency=urgency_label(task, now),
        suggested_start=suggest_start_time(task, now),
        first_step=first_step(task),
    )


def next_task(tasks: list[PlannerTask], now: datetime) -> TaskRecommendation | None:
    """Devuelve la acción principal (una sola tarea), o ``None`` si no hay."""
    actionable = [t for t in tasks if is_actionable(t)]
    if not actionable:
        return None
    best = max(actionable, key=lambda t: compute_score(t, now))
    return build_recommendation(best, now)
