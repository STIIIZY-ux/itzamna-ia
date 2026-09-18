"""Modo de emergencia (URGENCIA/RESCATE) determinista + IA."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.base import AIService
from app.ai.errors import AIServiceError
from app.ai.prompts import EMERGENCY_SYSTEM_PROMPT, build_task_context
from app.ai.types import AIMessage
from app.db.session import session_scope
from app.domain.enums import RiskLevel
from app.planner.engine import compute_score
from app.planner.risk import assess_risk
from app.repositories.accountability import AccountabilityRepository
from app.repositories.resources import ResourceRepository
from app.repositories.tasks import TaskRepository
from app.services.planning import PlanningService

logger = logging.getLogger(__name__)

_RISK_RANK = {
    RiskLevel.CRITICO: 3,
    RiskLevel.RIESGO: 2,
    RiskLevel.ATENCION: 1,
    RiskLevel.NORMAL: 0,
}


@dataclass(frozen=True)
class EmergencyAssessment:
    task_id: int | None
    title: str | None
    subject: str | None
    risk: RiskLevel | None
    due: datetime | None
    time_remaining: str | None
    missing: list[str]
    rescue_candidate: bool


class EmergencyService:
    """Analiza la situación crítica y prepara un plan de rescate por fases."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai: AIService | None,
    ) -> None:
        self._session_factory = session_factory
        self._ai = ai

    async def assess(self, user_id: int, now: datetime | None = None) -> EmergencyAssessment:
        now = now or datetime.now(timezone.utc)
        tasks = await PlanningService(self._session_factory).pending_tasks(user_id)
        if not tasks:
            return EmergencyAssessment(None, None, None, None, None, None, [], False)

        ranked = sorted(
            tasks,
            key=lambda t: (_RISK_RANK[assess_risk(t, now)], compute_score(t, now)),
            reverse=True,
        )
        best = ranked[0]
        risk = assess_risk(best, now)

        async with session_scope(self._session_factory) as session:
            rescue = bool(
                await AccountabilityRepository(session).list_rescue_candidates(user_id=user_id)
            )
            task = await TaskRepository(session).get(user_id=user_id, task_id=best.id)
            resources = (
                await ResourceRepository(session).list_for_task(best.id) if task else []
            )

        missing: list[str] = []
        if not best.instructions:
            missing.append("instrucciones")
        if task is not None and not task.description:
            missing.append("descripción")
        if not resources:
            missing.append("material de apoyo")

        return EmergencyAssessment(
            task_id=best.id,
            title=best.title,
            subject=best.subject,
            risk=risk,
            due=best.due_at,
            time_remaining=_time_remaining(best.due_at, now),
            missing=missing,
            rescue_candidate=rescue or risk is RiskLevel.CRITICO,
        )

    async def build_plan(self, user_id: int, now: datetime | None = None) -> str:
        assessment = await self.assess(user_id, now)
        if assessment.task_id is None:
            return "No hay ninguna actividad en estado crítico. 🎉"

        async with session_scope(self._session_factory) as session:
            task = await TaskRepository(session).get(
                user_id=user_id, task_id=assessment.task_id
            )
            resources = (
                await ResourceRepository(session).list_for_task(assessment.task_id)
                if task is not None
                else []
            )

        if self._ai is not None and task is not None:
            try:
                return await self._ai_plan(assessment, task, resources)
            except AIServiceError as exc:
                logger.warning("IA no disponible para emergencia: %s", exc)

        return self._deterministic_plan(assessment)

    async def _ai_plan(self, assessment: EmergencyAssessment, task, resources) -> str:
        if self._ai is None:
            return self._deterministic_plan(assessment)
        context = build_task_context(
            title=assessment.title or task.title,
            subject=assessment.subject,
            instructions=task.instructions,
            description=task.description,
            resources=[r.uri or r.name or "" for r in resources if r.uri or r.name],
            due=assessment.time_remaining,
        )
        messages = [
            AIMessage(role="system", content=EMERGENCY_SYSTEM_PROMPT),
            AIMessage(
                role="user",
                content=(
                    "Estoy en emergencia con esta actividad. Genera un plan por fases "
                    "(FASE 1 a FASE 6) accionable.\n\n" + context
                ),
            ),
        ]
        result = await self._ai.complete(messages, max_tokens=800)
        return result.content.strip()

    def _deterministic_plan(self, assessment: EmergencyAssessment) -> str:
        lines = [f"🚨 EMERGENCIA\nActividad: {assessment.title}"]
        if assessment.subject:
            lines.append(f"Materia: {assessment.subject}")
        lines.append(f"Tiempo restante: {assessment.time_remaining or 'sin fecha'}")
        lines.append("")
        lines.append("Plan de rescate:")
        lines.append("FASE 1 — Entender la actividad (instrucciones y descripción).")
        lines.append("FASE 2 — Reunir el material necesario.")
        lines.append("FASE 3 — Resolver en pasos pequeños.")
        lines.append("FASE 4 — Redactar/preparar el entregable.")
        lines.append("FASE 5 — Revisar requisitos y completar lo que falte.")
        lines.append("FASE 6 — Entregar el resultado.")
        if assessment.missing:
            lines.append("")
            lines.append("Necesito lo siguiente (envíalo por Telegram):")
            for item in assessment.missing:
                lines.append(f"• {item}")
        return "\n".join(lines)


def _time_remaining(due: datetime | None, now: datetime) -> str | None:
    if due is None:
        return None
    delta = due - now
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 0:
        return "vencida"
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} h"
    return f"{hours // 24} días"
