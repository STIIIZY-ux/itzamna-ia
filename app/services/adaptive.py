"""Inteligencia adaptativa determinista (estimaciones ajustadas por histórico)."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import TaskHistory
from app.db.session import session_scope
from app.domain.enums import HistoryEventType, TaskStatus
from app.repositories.tasks import TaskRepository

logger = logging.getLogger(__name__)

_STARTED_STATUSES = {"iniciada", "en_progreso", "compromiso"}
_ENDED_STATUSES = {"terminada", "entregada"}
_MIN_SAMPLES = 2
_MIN_FACTOR = 0.5
_MAX_FACTOR = 3.0


def actual_duration_minutes(history: list[TaskHistory], created_at: datetime) -> int | None:
    """Duración real estimada a partir del historial de estados."""
    start_at: datetime | None = None
    end_at: datetime | None = None
    for entry in sorted(history, key=lambda h: h.created_at):
        if entry.event_type is not HistoryEventType.ESTADO_CAMBIADO:
            continue
        if entry.to_value in _STARTED_STATUSES and start_at is None:
            start_at = entry.created_at
        if entry.to_value in _ENDED_STATUSES:
            end_at = entry.created_at
            break
    if end_at is None:
        return None
    start = start_at or created_at
    minutes = int((end_at - start).total_seconds() / 60)
    return max(0, minutes)


def correction_factor(samples: list[tuple[int, int]]) -> float | None:
    """Factor (actual/estimado) medio, acotado. ``None`` si no hay suficientes datos."""
    ratios = [actual / est for est, actual in samples if est and est > 0 and actual is not None]
    if len(ratios) < _MIN_SAMPLES:
        return None
    avg = sum(ratios) / len(ratios)
    return round(min(_MAX_FACTOR, max(_MIN_FACTOR, avg)), 2)


class AdaptiveEstimatesService:
    """Recomputa estimaciones ajustadas usando el histórico real.

    Nunca modifica ``estimated_minutes`` (estimación original); guarda
    ``adjusted_estimated_minutes`` y ``estimate_basis`` por separado.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def recompute(self, *, user_id: int) -> int:
        """Recalcula las estimaciones ajustadas. Devuelve cuántas tareas se actualizaron."""
        async with session_scope(self._session_factory) as session:
            repo = TaskRepository(session)
            tasks = await repo.list_tasks(user_id=user_id, limit=1000)

            samples_by_subject: dict[str | None, list[tuple[int, int]]] = {}
            for task in tasks:
                if task.status not in {TaskStatus.TERMINADA, TaskStatus.ENTREGADA}:
                    continue
                if not task.estimated_minutes:
                    continue
                actual = actual_duration_minutes(list(task.history), task.created_at)
                if actual is None:
                    continue
                key = task.subject.name if task.subject else None
                samples_by_subject.setdefault(key, []).append((task.estimated_minutes, actual))

            global_samples = [s for samples in samples_by_subject.values() for s in samples]
            global_factor = correction_factor(global_samples)

            updated = 0
            for task in tasks:
                if task.status in {TaskStatus.TERMINADA, TaskStatus.ENTREGADA}:
                    continue
                if not task.estimated_minutes:
                    continue
                key = task.subject.name if task.subject else None
                factor = correction_factor(samples_by_subject.get(key, [])) or global_factor
                if factor is None:
                    task.adjusted_estimated_minutes = None
                    task.estimate_basis = None
                    continue
                adjusted = max(1, round(task.estimated_minutes * factor))
                task.adjusted_estimated_minutes = adjusted
                task.estimate_basis = f"historical_x{factor}"
                updated += 1
            await session.flush()
        return updated
