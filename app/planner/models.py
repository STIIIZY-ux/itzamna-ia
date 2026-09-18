"""Estructuras de datos del planner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import TaskPriority, TaskStatus


@dataclass(frozen=True)
class PlannerTask:
    """Vista ligera de una tarea para el planner (desacoplada del ORM)."""

    id: int
    title: str
    subject: str | None
    due_at: datetime | None
    timezone: str | None
    priority: TaskPriority
    estimated_minutes: int | None
    status: TaskStatus
    instructions: str | None
    adjusted_estimated_minutes: int | None = None

    @classmethod
    def from_orm(cls, task) -> PlannerTask:
        return cls(
            id=task.id,
            title=task.title,
            subject=task.subject.name if task.subject else None,
            due_at=task.due_at,
            timezone=task.timezone,
            priority=task.priority,
            estimated_minutes=task.estimated_minutes,
            status=task.status,
            instructions=task.instructions,
            adjusted_estimated_minutes=getattr(task, "adjusted_estimated_minutes", None),
        )


@dataclass(frozen=True)
class TaskRecommendation:
    """Recomendación de una única acción principal."""

    task: PlannerTask
    score: float
    urgency: str
    suggested_start: datetime | None
    first_step: str
