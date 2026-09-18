"""Detección determinista de procrastinación (NORMAL/ATENCION/RIESGO)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import session_scope
from app.domain.enums import CommitmentStatus, RiskLevel, TaskStatus
from app.repositories.commitments import CommitmentRepository
from app.repositories.tasks import TaskRepository

_TERMINAL = {TaskStatus.TERMINADA, TaskStatus.ENTREGADA}


@dataclass(frozen=True)
class ProcrastinationReport:
    level: RiskLevel
    reasons: list[str]


class ProcrastinationService:
    """Detecta patrones de procrastinación con reglas explicables.

    Solo describe comportamiento observado; no diagnostica condiciones
    médicas ni psicológicas.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def detect(self, user_id: int, now: datetime | None = None) -> ProcrastinationReport:
        now = now or datetime.now(timezone.utc)

        async with session_scope(self._session_factory) as session:
            tasks = await TaskRepository(session).list_tasks(user_id=user_id, limit=1000)
            broken = await CommitmentRepository(session).count_by_status(
                user_id=user_id, status=CommitmentStatus.ACTIVO
            )

        reasons: list[str] = []
        pending = [t for t in tasks if t.status not in _TERMINAL]
        overdue = [t for t in pending if t.due_at is not None and t.due_at < now]

        if len(overdue) >= 2:
            reasons.append(f"{len(overdue)} tareas vencidas sin completar")

        # Tareas iniciadas demasiado cerca del deadline no se detectan aquí sin
        # marcas de tiempo de inicio; se aproxima con tareas pendientes próximas.
        close = [
            t
            for t in pending
            if t.due_at is not None and 0 < (t.due_at - now).total_seconds() < 24 * 3600
        ]
        if close:
            reasons.append(f"{len(close)} tareas pendientes a menos de 24h del vencimiento")

        if broken > 0:
            reasons.append(f"{broken} compromiso(s) activo(s) sin completar")

        level = RiskLevel.NORMAL
        if len(reasons) >= 2:
            level = RiskLevel.RIESGO
        elif len(reasons) == 1:
            level = RiskLevel.ATENCION
        return ProcrastinationReport(level=level, reasons=reasons)
