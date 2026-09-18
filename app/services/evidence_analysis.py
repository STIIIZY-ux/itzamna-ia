"""Análisis de evidencia mediante visión (AI)."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.base import AIService
from app.ai.prompts import VISION_SYSTEM_PROMPT, untrusted_block
from app.ai.types import AIImage, AIMessage
from app.db.models import Resource, ScheduledJob
from app.db.session import session_scope
from app.domain.enums import ResourceStatus
from app.repositories.accountability import AccountabilityRepository
from app.repositories.resources import ResourceRepository
from app.repositories.tasks import TaskRepository
from app.repositories.users import UserRepository
from app.storage.base import FileStorage

logger = logging.getLogger(__name__)

_TERMINAL = {ResourceStatus.VALID, ResourceStatus.INVALID, ResourceStatus.UNCERTAIN}


@dataclass(frozen=True)
class VisionResult:
    verdict: ResourceStatus
    confidence: float | None
    explanation: str


def _extract_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        # quita cercas de markdown ```json ... ```
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_verdict(content: str) -> VisionResult:
    data = _extract_json(content)
    verdict_raw = str(data.get("verdict", "uncertain")).lower()
    verdict = {
        "valid": ResourceStatus.VALID,
        "invalid": ResourceStatus.INVALID,
    }.get(verdict_raw, ResourceStatus.UNCERTAIN)
    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)):
        confidence = float(confidence)
    else:
        confidence = None
    explanation = str(data.get("explanation", "") or "")
    return VisionResult(verdict=verdict, confidence=confidence, explanation=explanation)


class EvidenceAnalysisService:
    """Analiza la evidencia almacenada (visión) y persiste el veredicto."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: FileStorage,
        ai: AIService | None,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._ai = ai

    async def analyze(self, *, user_id: int, resource_id: int) -> VisionResult:
        async with session_scope(self._session_factory) as session:
            repo = ResourceRepository(session)
            resource = await repo.get_by_id_scoped(user_id=user_id, resource_id=resource_id)
            if resource is None:
                raise LookupError(f"Recurso {resource_id} no encontrado")

            existing = _existing_verdict(resource)
            if existing is not None:
                return existing

            task = None
            if resource.task_id is not None:
                task = await TaskRepository(session).get(user_id=user_id, task_id=resource.task_id)

            result = await self._run_vision(resource, task)

            await repo.update(
                resource,
                status=result.verdict,
                metadata={
                    "analysis": {
                        "verdict": result.verdict.value,
                        "confidence": result.confidence,
                        "explanation": result.explanation,
                    }
                },
            )

            if result.verdict is ResourceStatus.VALID and resource.task_id is not None:
                acc = await AccountabilityRepository(session).get(
                    user_id=user_id, task_id=resource.task_id
                )
                if acc is not None:
                    await AccountabilityRepository(session).update(acc, rescue_candidate=False)

            return result

    async def _run_vision(self, resource: Resource, task) -> VisionResult:
        if self._ai is None:
            return VisionResult(ResourceStatus.UNCERTAIN, None, "IA no disponible")
        if resource.storage_key is None:
            return VisionResult(ResourceStatus.UNCERTAIN, None, "archivo ausente")
        try:
            data = self._storage.load(resource.storage_key)
        except Exception as exc:  # noqa: BLE001 - archivo corrupto/inexistente
            logger.warning("No se pudo leer la evidencia %s: %s", resource.id, exc)
            return VisionResult(ResourceStatus.UNCERTAIN, None, "no se pudo leer la imagen")

        task_block = (
            untrusted_block(
                "TAREA",
                f"{task.title}\n{task.instructions or ''}",
            )
            if task is not None
            else untrusted_block("TAREA", "(sin tarea asociada)")
        )
        prompt = (
            "Analiza la imagen adjunta y determina si proporciona evidencia razonable "
            "de que el usuario está trabajando en la tarea.\n\n" + task_block
        )
        messages = [
            AIMessage(role="system", content=VISION_SYSTEM_PROMPT),
            AIMessage(
                role="user",
                content=prompt,
                image=AIImage(data=data, content_type=resource.content_type or "image/jpeg"),
            ),
        ]
        result = await self._ai.complete(messages, max_tokens=200)
        return _parse_verdict(result.content)


def _existing_verdict(resource: Resource) -> VisionResult | None:
    if resource.status not in _TERMINAL:
        return None
    analysis = (resource.file_metadata or {}).get("analysis") or {}
    verdict = resource.status
    confidence = analysis.get("confidence")
    explanation = analysis.get("explanation") or ""
    return VisionResult(verdict=verdict, confidence=confidence, explanation=str(explanation))


def verdict_message(result: VisionResult) -> str:
    if result.verdict is ResourceStatus.VALID:
        return f"✅ Evidencia válida: {result.explanation or 'se observa trabajo relacionado.'}"
    if result.verdict is ResourceStatus.INVALID:
        return f"❌ Evidencia no válida: {result.explanation or 'no se observa relación con la actividad.'}"
    return f"❓ No pude determinar: {result.explanation or 'envía otra foto.'}"


def make_evidence_dispatcher(
    send_message: Callable[[int, str], Awaitable[None]],
    session_factory: async_sessionmaker[AsyncSession],
    storage: FileStorage,
    ai: AIService | None,
) -> Callable[[ScheduledJob], Awaitable[bool]]:
    """Construye el callable que procesa jobs ``ANALYZE_EVIDENCE``."""

    async def dispatch(job: ScheduledJob) -> bool:
        payload = job.payload or {}
        resource_id = payload.get("resource_id")
        if resource_id is None:
            return False

        result = await EvidenceAnalysisService(session_factory, storage, ai).analyze(
            user_id=job.user_id, resource_id=resource_id
        )

        async with session_scope(session_factory) as session:
            user = await UserRepository(session).get(job.user_id)

        if user is not None:
            await send_message(user.telegram_id, verdict_message(result))
            return True
        return False

    return dispatch
