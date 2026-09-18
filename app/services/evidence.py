"""Servicio de evidencia y archivos subidos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Resource
from app.domain.enums import AccountabilityState, JobKind, ResourceStatus, ResourceType
from app.repositories.accountability import AccountabilityRepository
from app.repositories.commitments import CommitmentRepository
from app.repositories.resources import ResourceRepository
from app.scheduler.service import SchedulerService
from app.storage.base import FileStorage
from app.storage.validation import (
    FileValidationError,
    detect_content_type,
    extension_for,
    is_image,
)


class FileTooLargeError(Exception):
    """El archivo supera el límite de tamaño permitido."""


class TooManyEvidenceError(Exception):
    """La tarea ya alcanzó el máximo de evidencias permitidas."""


@dataclass(frozen=True)
class StoredFile:
    resource: Resource
    created: bool  # False si ya existía (deduplicación)


def classify_content(content_type: str) -> tuple[ResourceType, ResourceStatus]:
    """Determina tipo de recurso y estado inicial a partir del contenido."""
    if is_image(content_type):
        return ResourceType.EVIDENCIA, ResourceStatus.PENDING_ANALYSIS
    return ResourceType.PDF, ResourceStatus.RECEIVED


class EvidenceService:
    """Recibe, valida, almacena y registra archivos/evidencia."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: FileStorage,
        *,
        max_file_bytes: int = 20 * 1024 * 1024,
        max_evidence_per_task: int = 10,
        scheduler: SchedulerService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._max_file_bytes = max_file_bytes
        self._max_evidence_per_task = max_evidence_per_task
        self._scheduler = scheduler

    async def resolve_task(self, user_id: int) -> int | None:
        """Determina la tarea a la que asociar evidencia (determinista).

        1. Tarea en ``AWAITING_EVIDENCE``.
        2. Tarea con un compromiso activo.
        En cualquier otro caso devuelve ``None`` (no se adivina).
        """
        async with self._session_factory() as session:
            awaiting = await AccountabilityRepository(session).find_by_state(
                user_id=user_id, state=AccountabilityState.AWAITING_EVIDENCE
            )
            if awaiting:
                return awaiting[0].task_id
            active = await CommitmentRepository(session).list_active_for_user(user_id=user_id)
            if active:
                return active[0].task_id
            return None

    async def store_upload(
        self,
        *,
        user_id: int,
        task_id: int | None,
        file_unique_id: str,
        file_id: str | None,
        name: str | None,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> StoredFile:
        """Almacena un archivo subido y crea su registro (idempotente).

        Valida contenido (magic bytes) y tamaño antes de cualquier efecto.
        Si el registro en BD falla, se elimina el archivo almacenado.
        """
        content_type = detect_content_type(data)
        if content_type is None:
            raise FileValidationError("Tipo de archivo no permitido")

        if len(data) > self._max_file_bytes:
            raise FileTooLargeError(
                f"Archivo de {len(data)} bytes supera el límite de {self._max_file_bytes}"
            )

        resource_type, status = classify_content(content_type)

        async with self._session_factory() as session:
            repo = ResourceRepository(session)

            existing = await repo.get_by_file_unique_id(user_id, file_unique_id)
            if existing is not None:
                return StoredFile(resource=existing, created=False)

            if task_id is not None:
                count = await repo.count_for_task(user_id=user_id, task_id=task_id)
                if count >= self._max_evidence_per_task:
                    raise TooManyEvidenceError(
                        f"La tarea {task_id} alcanzó el máximo de evidencias"
                    )

            storage_key = self._storage.save(data, extension_for(content_type))
            try:
                resource = await repo.add(
                    resource_type=resource_type,
                    task_id=task_id,
                    user_id=user_id,
                    name=name,
                    external_id=file_id,
                    file_unique_id=file_unique_id,
                    storage_key=storage_key,
                    content_type=content_type,
                    size_bytes=len(data),
                    status=status,
                    metadata=metadata,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                self._storage.delete(storage_key)
                raise

            if self._scheduler is not None and resource_type is ResourceType.EVIDENCIA:
                await self._schedule_analysis(user_id=user_id, resource=resource)

            return StoredFile(resource=resource, created=True)

    async def _schedule_analysis(self, *, user_id: int, resource: Resource) -> None:
        if self._scheduler is None:
            return
        await self._scheduler.schedule(
            user_id=user_id,
            kind=JobKind.ANALYZE_EVIDENCE,
            scheduled_at=datetime.now(timezone.utc),
            dedup_key=f"analyze:{resource.id}",
            task_id=resource.task_id,
            payload={"resource_id": resource.id, "task_id": resource.task_id},
        )
