"""Modelo de recurso/evidencia asociado a una tarea."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_values
from app.domain.enums import ResourceStatus, ResourceType

if TYPE_CHECKING:
    from .task import Task
    from .user import User


class Resource(Base):
    """Recurso o evidencia asociada a una tarea.

    Representa tanto enlaces de Calendar como archivos subidos (evidencia,
    PDF, imágenes). Para archivos binarios, ``storage_key`` apunta al objeto
    almacenado (nunca se guarda el binario en PostgreSQL).
    """

    __tablename__ = "resources"
    __table_args__ = (
        Index(
            "uq_resources_file_unique_id",
            "file_unique_id",
            unique=True,
            postgresql_where="file_unique_id IS NOT NULL",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    resource_type: Mapped[ResourceType] = mapped_column(
        Enum(
            ResourceType,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(255))
    uri: Mapped[str | None] = mapped_column(String(2048))
    external_id: Mapped[str | None] = mapped_column(String(255))
    file_unique_id: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(127))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[ResourceStatus | None] = mapped_column(
        Enum(
            ResourceStatus,
            native_enum=False,
            length=50,
            validate_strings=True,
            values_callable=enum_values,
        )
    )
    file_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[Task | None] = relationship(back_populates="resources")
    user: Mapped[User | None] = relationship()
