"""Tests del análisis de evidencia (visión)."""

import pytest

from app.domain.enums import ResourceStatus
from app.services.evidence import EvidenceService
from app.services.evidence_analysis import EvidenceAnalysisService, verdict_message
from app.storage.local import LocalFileStorage
from tests.fake_ai import FakeAIService

JPEG = b"\xff\xd8\xff" + b"\x00" * 64


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=1100)
    return user.id


async def _store_evidence(session_factory, tmp_path, user_id, task_id) -> int:
    storage = LocalFileStorage(tmp_path)
    service = EvidenceService(session_factory, storage)
    stored = await service.store_upload(
        user_id=user_id, task_id=task_id, file_unique_id="fu", file_id="f", name=None, data=JPEG
    )
    return stored.resource.id


def _analyzer(session_factory, tmp_path, ai):
    return EvidenceAnalysisService(session_factory, LocalFileStorage(tmp_path), ai)


async def test_analyze_valid(session, session_factory, tmp_path, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    resource_id = await _store_evidence(session_factory, tmp_path, user_id, task.id)

    ai = FakeAIService(['{"verdict":"valid","confidence":0.9,"explanation":"se ve el documento"}'])
    result = await _analyzer(session_factory, tmp_path, ai).analyze(
        user_id=user_id, resource_id=resource_id
    )
    assert result.verdict is ResourceStatus.VALID
    assert result.confidence == 0.9


async def test_analyze_invalid(session, session_factory, tmp_path, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    resource_id = await _store_evidence(session_factory, tmp_path, user_id, task.id)

    ai = FakeAIService(['{"verdict":"invalid","confidence":0.8,"explanation":"no relacionado"}'])
    result = await _analyzer(session_factory, tmp_path, ai).analyze(
        user_id=user_id, resource_id=resource_id
    )
    assert result.verdict is ResourceStatus.INVALID


async def test_analyze_uncertain_on_bad_json(session, session_factory, tmp_path, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    resource_id = await _store_evidence(session_factory, tmp_path, user_id, task.id)

    ai = FakeAIService(["no soy json"])
    result = await _analyzer(session_factory, tmp_path, ai).analyze(
        user_id=user_id, resource_id=resource_id
    )
    assert result.verdict is ResourceStatus.UNCERTAIN


async def test_analyze_no_ai_is_uncertain(session, session_factory, tmp_path, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    resource_id = await _store_evidence(session_factory, tmp_path, user_id, task.id)

    result = await _analyzer(session_factory, tmp_path, None).analyze(
        user_id=user_id, resource_id=resource_id
    )
    assert result.verdict is ResourceStatus.UNCERTAIN


async def test_analyze_is_idempotent(session, session_factory, tmp_path, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    resource_id = await _store_evidence(session_factory, tmp_path, user_id, task.id)

    ai = FakeAIService(['{"verdict":"valid","confidence":0.9,"explanation":"ok"}'])
    analyzer = _analyzer(session_factory, tmp_path, ai)
    await analyzer.analyze(user_id=user_id, resource_id=resource_id)
    # Segunda llamada no debe volver a llamar al modelo.
    result = await analyzer.analyze(user_id=user_id, resource_id=resource_id)
    assert result.verdict is ResourceStatus.VALID
    assert len(ai.calls) == 1


async def test_analyze_missing_file(session, session_factory, tmp_path, user_service, task_service) -> None:
    user_id = await _make_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="T")
    resource_id = await _store_evidence(session_factory, tmp_path, user_id, task.id)

    # Elimina el archivo del disco.
    from app.db.session import session_scope
    from app.repositories.resources import ResourceRepository

    async with session_scope(session_factory) as s:
        resource = await ResourceRepository(s).get_by_id_scoped(user_id=user_id, resource_id=resource_id)
        LocalFileStorage(tmp_path).delete(resource.storage_key)

    ai = FakeAIService(['{"verdict":"valid"}'])
    result = await _analyzer(session_factory, tmp_path, ai).analyze(
        user_id=user_id, resource_id=resource_id
    )
    assert result.verdict is ResourceStatus.UNCERTAIN


async def test_analyze_resource_not_found(session, session_factory, tmp_path, user_service) -> None:
    user_id = await _make_user(user_service)
    with pytest.raises(LookupError):
        await _analyzer(session_factory, tmp_path, FakeAIService()).analyze(
            user_id=user_id, resource_id=9999
        )


def test_verdict_message() -> None:
    assert "válida" in verdict_message_from_status(ResourceStatus.VALID)
    assert "no válida" in verdict_message_from_status(ResourceStatus.INVALID)
    assert "determinar" in verdict_message_from_status(ResourceStatus.UNCERTAIN)


def verdict_message_from_status(status: ResourceStatus) -> str:
    from app.services.evidence_analysis import VisionResult

    return verdict_message(VisionResult(verdict=status, confidence=None, explanation=""))
