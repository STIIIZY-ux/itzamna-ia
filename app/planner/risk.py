"""Detección determinista de riesgo de una tarea."""

from __future__ import annotations

from datetime import datetime

from app.domain.enums import RiskLevel, TaskPriority, TaskStatus

from .models import PlannerTask

_HIGH_PRIORITY = {TaskPriority.ALTA, TaskPriority.URGENTE}
_STARTED_STATES = {TaskStatus.INICIADA, TaskStatus.EN_PROGRESO, TaskStatus.TERMINADA}


def assess_risk(
    task: PlannerTask,
    now: datetime,
    *,
    has_broken_commitment: bool = False,
) -> RiskLevel:
    """Clasifica el riesgo de una tarea (determinista, sin IA)."""
    if task.due_at is None:
        return RiskLevel.NORMAL

    minutes_left = (task.due_at - now).total_seconds() / 60
    high = task.priority in _HIGH_PRIORITY
    started = task.status in _STARTED_STATES

    if minutes_left <= 0:
        return RiskLevel.CRITICO
    if high and not started and minutes_left <= 60 * 24:
        return RiskLevel.CRITICO
    if has_broken_commitment:
        return RiskLevel.RIESGO
    if minutes_left <= 60 * 24:
        return RiskLevel.RIESGO
    if high and minutes_left <= 72 * 60:
        return RiskLevel.RIESGO
    if minutes_left <= 72 * 60:
        return RiskLevel.ATENCION
    if high and minutes_left <= 7 * 24 * 60:
        return RiskLevel.ATENCION
    return RiskLevel.NORMAL
