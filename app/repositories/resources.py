"""Repositorio de recursos/evidencias asociados a tareas."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Resource
from app.domain.enums import ResourceStatus, ResourceType


class ResourceRepository:
    """Acceso a datos de :class:`Resource`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        resource_type: ResourceType,
        task_id: int | None = None,
        user_id: int | None = None,
        name: str | None = None,
        uri: str | None = None,
        external_id: str | None = None,
        file_unique_id: str | None = None,
        storage_key: str | None = None,
        content_type: str | None = None,
        size_bytes: int | None = None,
        status: ResourceStatus | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Resource:
        resource = Resource(
            resource_type=resource_type,
            task_id=task_id,
            user_id=user_id,
            name=name,
            uri=uri,
            external_id=external_id,
            file_unique_id=file_unique_id,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size_bytes,
            status=status,
            file_metadata=metadata,
        )
        self._session.add(resource)
        await self._session.flush()
        return resource

    async def list_for_task(self, task_id: int) -> list[Resource]:
        result = await self._session.execute(
            select(Resource).where(Resource.task_id == task_id).order_by(Resource.id)
        )
        return list(result.scalars().all())

    async def get_by_uri(self, task_id: int, uri: str) -> Resource | None:
        result = await self._session.execute(
            select(Resource).where(Resource.task_id == task_id, Resource.uri == uri)
        )
        return result.scalar_one_or_none()

    async def get_by_file_unique_id(self, user_id: int, file_unique_id: str) -> Resource | None:
        result = await self._session.execute(
            select(Resource).where(
                Resource.user_id == user_id, Resource.file_unique_id == file_unique_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_scoped(self, *, user_id: int, resource_id: int) -> Resource | None:
        result = await self._session.execute(
            select(Resource).where(Resource.id == resource_id, Resource.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        resource: Resource,
        *,
        status: ResourceStatus | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Resource:
        if status is not None:
            resource.status = status
        if metadata is not None:
            resource.file_metadata = metadata
        await self._session.flush()
        return resource

    async def count_for_task(self, *, user_id: int, task_id: int) -> int:
        result = await self._session.execute(
            select(func.count(Resource.id)).where(
                Resource.user_id == user_id, Resource.task_id == task_id
            )
        )
        return int(result.scalar_one())
