"""Tests del Learning Engine (dominio, conceptos, flashcards, repaso, SRS)."""

from datetime import datetime, timedelta, timezone

from app.services.learning.concepts import ConceptService
from app.services.learning.flashcards import FlashcardService
from app.services.learning.mastery import update_mastery
from app.services.learning.review import ReviewService
from app.services.learning.spaced_repetition import next_review_at


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=1300)
    return user.id


# --- dominio (puro) ---

def test_update_mastery_bounded_increase() -> None:
    assert update_mastery(0.5, correct=True, difficulty=2) < 0.7
    assert update_mastery(0.95, correct=True, difficulty=3) <= 1.0


def test_update_mastery_bounded_decrease() -> None:
    assert update_mastery(0.5, correct=False, difficulty=2) > 0.3
    assert update_mastery(0.0, correct=False) == 0.0


def test_next_review_incorrect_short() -> None:
    now = datetime.now(timezone.utc)
    assert next_review_at(now, correct=False) == now + timedelta(minutes=30)


def test_next_review_correct_grows_with_mastery() -> None:
    now = datetime.now(timezone.utc)
    low = next_review_at(now, correct=True, difficulty=2, mastery=0.0)
    high = next_review_at(now, correct=True, difficulty=2, mastery=1.0)
    assert high > low


# --- conceptos ---

async def test_concept_get_or_create_dedup(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = ConceptService(session_factory)
    a = await service.get_or_create(user_id=user_id, name="Bucles")
    b = await service.get_or_create(user_id=user_id, name="bucles")
    assert a.id == b.id


async def test_record_answer_updates_mastery(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = ConceptService(session_factory)
    concept = await service.get_or_create(user_id=user_id, name="Condicionales")
    updated = await service.record_answer(user_id=user_id, concept_id=concept.id, correct=True, difficulty=3)
    assert updated.mastery > concept.mastery
    assert updated.next_review_at is not None


async def test_list_weak(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = ConceptService(session_factory)
    await service.get_or_create(user_id=user_id, name="Fuerte")
    await service.get_or_create(user_id=user_id, name="Debil")
    # Baja el dominio de "Debil" con varias respuestas incorrectas.
    weak = await service.get_or_create(user_id=user_id, name="Debil")
    for _ in range(3):
        weak = await service.record_answer(user_id=user_id, concept_id=weak.id, correct=False, difficulty=1)

    weak_list = await service.list_weak(user_id=user_id, threshold=0.6)
    names = [c.name for c in weak_list]
    assert "Debil" in names


# --- flashcards ---

async def test_flashcard_create_and_review(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = FlashcardService(session_factory)
    card = await service.create(user_id=user_id, front="¿Qué es un bucle?", back="Repetición controlada")
    reviewed = await service.review(user_id=user_id, card_id=card.id, correct=True)
    assert reviewed.next_review_at is not None
    assert reviewed.last_reviewed_at is not None


async def test_flashcard_review_missing_raises(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = FlashcardService(session_factory)
    import pytest

    with pytest.raises(LookupError):
        await service.review(user_id=user_id, card_id=9999, correct=True)


# --- repaso ---

async def test_review_picks_due_and_weak(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    concept_service = ConceptService(session_factory)

    # Un concepto débil.
    weak = await concept_service.get_or_create(user_id=user_id, name="Apuntadores")
    for _ in range(3):
        weak = await concept_service.record_answer(user_id=user_id, concept_id=weak.id, correct=False, difficulty=1)

    items = await ReviewService(session_factory).pick(user_id=user_id, limit=5)
    assert any(i.kind == "concept" and "Apuntadores" in i.front for i in items)
