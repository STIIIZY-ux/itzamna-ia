"""Briefings diario/nocturno y auditoría semanal."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.base import AIService
from app.ai.errors import AIServiceError
from app.ai.prompts import untrusted_block
from app.ai.types import AIMessage
from app.scheduler.messages import format_due
from app.services.learning.review import ReviewService
from app.services.planning import PlanningService
from app.services.statistics import PeriodStats, StatisticsService

logger = logging.getLogger(__name__)


class BriefingService:
    """Genera resúmenes diarios, nocturnos y auditorías semanales."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai: AIService | None,
        timezone: str,
    ) -> None:
        self._session_factory = session_factory
        self._ai = ai
        self._timezone = timezone

    async def daily_briefing(self, user_id: int, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        rec = await PlanningService(self._session_factory).next_recommendation(user_id)
        stats = await StatisticsService(self._session_factory).daily(user_id, date=now)
        review = await ReviewService(self._session_factory).pick(user_id=user_id, limit=3)

        lines = ["☀️ Resumen del día"]
        if rec is not None:
            due = format_due(rec.task.due_at, self._timezone)
            lines.append(f"🎯 Prioridad: {rec.task.title} (vence: {due})")
        lines.append(f"📋 Tareas de hoy: {stats.tasks_total}")
        lines.append(f"⏰ Próximas entregas: {stats.tasks_total}")
        if review:
            lines.append(f"🧠 Repaso pendiente: {len(review)} ítems")
        return "\n".join(lines)

    async def nocturnal_summary(self, user_id: int, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        stats = await StatisticsService(self._session_factory).daily(user_id, date=now)
        rec = await PlanningService(self._session_factory).next_recommendation(user_id)

        lines = ["🌙 Resumen del día"]
        lines.append(f"✅ Completadas: {stats.tasks_completed}")
        lines.append(f"⚠️ Atrasadas: {stats.tasks_overdue}")
        lines.append(f"📌 Pendientes: {stats.tasks_total - stats.tasks_completed}")
        if rec is not None:
            lines.append(f"🎯 Para mañana: {rec.task.title}")
        return "\n".join(lines)

    async def weekly_audit(self, user_id: int, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        stats = await StatisticsService(self._session_factory).weekly(user_id, now=now)

        data = (
            f"Tareas (semana): total={stats.tasks_total}, completadas={stats.tasks_completed}, "
            f"atrasadas={stats.tasks_overdue}, a tiempo={stats.on_time}. "
            f"Quizzes: {stats.quizzes_taken}. Dominio medio: "
            f"{round(stats.avg_mastery, 2) if stats.avg_mastery is not None else 'n/a'}. "
            f"Conceptos débiles: {stats.weak_concepts}."
        )
        conclusion = self._deterministic_conclusion(stats)

        if self._ai is not None:
            try:
                ai_conclusion = await self._ai_conclusion(data)
                if ai_conclusion:
                    conclusion = ai_conclusion
            except AIServiceError as exc:
                logger.warning("IA no disponible para auditoría: %s", exc)

        return f"📊 Auditoría semanal\n\n{conclusion}\n\nDatos:\n{data}"

    async def _ai_conclusion(self, data: str) -> str:
        if self._ai is None:
            return ""
        result = await self._ai.complete(
            [
                AIMessage(
                    role="system",
                    content=(
                        "Eres el revisor académico de Itzamná IA. Interpreta SOLO los datos "
                        "proporcionados; no los inventes. Responde en 1-2 frases en español."
                    ),
                ),
                AIMessage(
                    role="user",
                    content=f"Genera una conclusión breve:\n\n{untrusted_block('ESTADÍSTICAS', data)}",
                ),
            ],
            max_tokens=150,
        )
        return result.content.strip()

    def _deterministic_conclusion(self, stats: PeriodStats) -> str:
        if stats.tasks_overdue > 0:
            return f"El principal problema fue dejar {stats.tasks_overdue} tarea(s) sin completar a tiempo."
        if stats.tasks_completed > 0:
            return f"Buen cumplimiento: {stats.tasks_completed} tarea(s) completadas en la semana."
        return "Sin datos suficientes para una conclusión."
