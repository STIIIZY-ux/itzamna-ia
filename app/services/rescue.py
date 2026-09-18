"""Ofrecimiento de modo rescate (no se activa automáticamente)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import session_scope
from app.domain.enums import RiskLevel
from app.planner.risk import assess_risk
from app.repositories.accountability import AccountabilityRepository
from app.services.planning import PlanningService

from .emergency import _time_remaining


@dataclass(frozen=True)
class RescueOffer:
    task_id: int
    title: str
    time_remaining: str
    reason: str


class RescueService:
    """Detecta candidatos a rescate y genera una oferta (requiere confirmación)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def offer(self, user_id: int, now: datetime | None = None) -> RescueOffer | None:
        now = now or datetime.now(timezone.utc)
        tasks = await PlanningService(self._session_factory).pending_tasks(user_id)
        if not tasks:
            return None

        async with session_scope(self._session_factory) as session:
            rescue_ids = {
                a.task_id
                for a in await AccountabilityRepository(session).list_rescue_candidates(
                    user_id=user_id
                )
            }

        ranked = sorted(tasks, key=lambda t: assess_risk(t, now).value, reverse=True)
        best = ranked[0]
        risk = assess_risk(best, now)

        if risk is not RiskLevel.CRITICO and best.id not in rescue_ids:
            return None

        reason = "riesgo crítico" if risk is RiskLevel.CRITICO else "marcada como candidata a rescate"
        return RescueOffer(
            task_id=best.id,
            title=best.title,
            time_remaining=_time_remaining(best.due_at, now) or "sin fecha",
            reason=reason,
        )
