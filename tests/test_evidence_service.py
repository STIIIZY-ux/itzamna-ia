"""Tests del servicio de evidencia."""

import pytest

from app.domain.enums import ResourceStatus, ResourceType
from app.repositories.resources import ResourceRepository
from app.services.accountability import AccountabilityService
from app.services.evidence import (
    EvidenceService,
    FileTooLargeError,
    FileValidationError,
    TooManyEvidenceError,
)
from app.storage.local import LocalFileStorage

JPEG = b"\xff\xd8\xff" + b"\x00" * 64
PDF = b"%PDF-1.4" + b"\x00" * 64


@pytest.fixture
def service(session_factory, tmp_path):
    return EvidenceService(
        session_factory,
        LocalFileStorage(tmp_path),
        max_file_bytes=1024 * 1024,
        max_evidence_per_task=5,
    )


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=1000)
    return user.id


async def test_store_image_evidence(session, service, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")

    stored = await service.store_upload(
        user_id=user_id,
        task_id=task.id,
        file_unique_id="fu1",
        file_id="f1",
        name=None,
        data=JPEG,
    )
    assert stored.created is True
    resource = stored.resource
    assert resource.resource_type is ResourceType.EVIDENCIA
    assert resource.status is ResourceStatus.PENDING_ANALYSIS
    assert resource.content_type == "image/jpeg"
    assert resource.storage_key is not None
    assert resource.size_bytes == len(JPEG)


async def test_store_pdf(session, service, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    stored = await service.store_upload(
        user_id=user_id, task_id=task.id, file_unique_id="fu2", file_id="f2", name="x.pdf", data=PDF
    )
    assert stored.resource.resource_type is ResourceType.PDF
    assert stored.resource.status is ResourceStatus.RECEIVED


async def test_dedup_by_file_unique_id(session, service, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")

    first = await service.store_upload(
        user_id=user_id, task_id=task.id, file_unique_id="fu3", file_id="f3", name=None, data=JPEG
    )
    second = await service.store_upload(
        user_id=user_id, task_id=task.id, file_unique_id="fu3", file_id="f3", name=None, data=JPEG
    )
    assert first.created is True
    assert second.created is False
    assert first.resource.id == second.resource.id


async def test_invalid_content_rejected(session, service, user_service) -> None:
    user_id = await _make_user(user_service)
    with pytest.raises(FileValidationError):
        await service.store_upload(
            user_id=user_id, task_id=None, file_unique_id="fu4", file_id="f4", name=None, data=b"basura"
        )


async def test_too_large_rejected(session, service, user_service) -> None:
    user_id = await _make_user(user_service)
    big = JPEG + b"\x00" * (1024 * 1024 + 10)
    with pytest.raises(FileTooLargeError):
        await service.store_upload(
            user_id=user_id, task_id=None, file_unique_id="fu5", file_id="f5", name=None, data=big
        )


async def test_too_many_evidence(session, session_factory, tmp_path, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    limited = EvidenceService(
        session_factory, LocalFileStorage(tmp_path), max_file_bytes=1024 * 1024, max_evidence_per_task=1
    )
    await limited.store_upload(
        user_id=user_id, task_id=task.id, file_unique_id="a1", file_id="a1", name=None, data=JPEG
    )
    with pytest.raises(TooManyEvidenceError):
        await limited.store_upload(
            user_id=user_id, task_id=task.id, file_unique_id="a2", file_id="a2", name=None, data=JPEG
        )


async def test_store_unassociated(session, service, user_service) -> None:
    user_id = await _make_user(user_service)
    stored = await service.store_upload(
        user_id=user_id, task_id=None, file_unique_id="fu6", file_id="f6", name=None, data=JPEG
    )
    assert stored.resource.task_id is None


async def test_rollback_cleans_file(
    session, session_factory, tmp_path, user_service, monkeypatch
) -> None:
    user_id = await _make_user(user_service)
    storage = LocalFileStorage(tmp_path)
    service = EvidenceService(session_factory, storage, max_file_bytes=1024 * 1024)

    async def fail_add(self, **kwargs):
        raise RuntimeError("fallo de BD")

    monkeypatch.setattr(ResourceRepository, "add", fail_add)

    with pytest.raises(RuntimeError):
        await service.store_upload(
            user_id=user_id, task_id=None, file_unique_id="fu7", file_id="f7", name=None, data=JPEG
        )

    # No debe quedar archivo huérfano.
    assert list(tmp_path.iterdir()) == []


async def test_resolve_task_prefers_awaiting_evidence(
    session, session_factory, service, user_service, task_service
) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    await AccountabilityService(session_factory).mark_evidence_requested(user_id=user_id, task_id=task.id)

    assert await service.resolve_task(user_id) == task.id


async def test_resolve_task_falls_back_to_commitment(
    session, session_factory, service, user_service, task_service
) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    await AccountabilityService(session_factory).record_commitment(user_id=user_id, task_id=task.id)

    assert await service.resolve_task(user_id) == task.id


async def test_resolve_task_none(session, service, user_service) -> None:
    user_id = await _make_user(user_service)
    assert await service.resolve_task(user_id) is None
