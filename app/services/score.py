"""Academic Score: métrica interna determinista y explicable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import session_scope
from app.domain.enums import CommitmentStatus, TaskStatus
from app.repositories.commitments import CommitmentRepository
from app.repositories.learning import ConceptRepository, QuizAnswerRepository
from app.repositories.tasks import TaskRepository

_TERMINAL = {TaskStatus.TERMINADA, TaskStatus.ENTREGADA}

#: Pesos (suman 1.0). No es una calificación universitaria.
_WEIGHTS = {
    "puntualidad": 0.30,
    "completitud": 0.20,
    "dominio": 0.25,
    "quizzes": 0.15,
    "constancia": 0.10,
}


@dataclass(frozen=True)
class AcademicScore:
    score: int  # 0-100
    breakdown: dict[str, int]  # componente -> 0-100


def _fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return min(1.0, max(0.0, numerator / denominator))


class AcademicScoreService:
    """Calcula el Academic Score (0-100) a partir de datos reales."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def compute(self, user_id: int, now: datetime | None = None) -> AcademicScore:
        now = now or datetime.now(timezone.utc)

        async with session_scope(self._session_factory) as session:
            tasks = await TaskRepository(session).list_tasks(user_id=user_id, limit=1000)
            avg_mastery = await ConceptRepository(session).average_mastery(user_id=user_id)
            quiz_avg = await QuizAnswerRepository(session).average_correct(user_id=user_id)
            completed_commitments = await CommitmentRepository(session).count_by_status(
                user_id=user_id, status=CommitmentStatus.COMPLETADO
            )
            total_commitments = completed_commitments + await CommitmentRepository(session).count_by_status(
                user_id=user_id, status=CommitmentStatus.ACTIVO
            ) + await CommitmentRepository(session).count_by_status(
                user_id=user_id, status=CommitmentStatus.CANCELADO
            )

        completed = [t for t in tasks if t.status in _TERMINAL]
        on_time = sum(
            1 for t in completed if t.due_at is None or t.due_at >= now
        )
        total = len(tasks)

        punctuality = _fraction(on_time, len(completed))
        completion = _fraction(len(completed), total)
        mastery = avg_mastery if avg_mastery is not None else 0.0
        quiz = quiz_avg if quiz_avg is not None else 0.0
        consistency = _fraction(completed_commitments, total_commitments)

        components = {
            "puntualidad": punctuality,
            "completitud": completion,
            "dominio": mastery,
            "quizzes": quiz,
            "constancia": consistency,
        }
        score = round(sum(components[k] * _WEIGHTS[k] for k in _WEIGHTS) * 100)
        breakdown = {k: round(components[k] * 100) for k in _WEIGHTS}
        return AcademicScore(score=score, breakdown=breakdown)
