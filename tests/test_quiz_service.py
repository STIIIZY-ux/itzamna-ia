"""Tests del servicio de quizzes y evaluación."""

from app.domain.enums import QuizStatus, QuizType
from app.services.learning.quizzes import QuizService
from tests.fake_ai import FakeAIService

MC_QUESTION = {
    "question_type": "multiple_choice",
    "prompt": "¿Qué es un bucle?",
    "options": ["Repetición", "Condición", "Función"],
    "correct_index": 0,
    "explanation": "Un bucle repite instrucciones.",
}
TF_QUESTION = {
    "question_type": "true_false",
    "prompt": "Un bucle se ejecuta una sola vez.",
    "expected_answer": "falso",
    "explanation": "Un bucle repite.",
}


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=1400)
    return user.id


async def test_create_quiz_and_answer_mc(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = QuizService(session_factory, None)
    quiz = await service.create_quiz(
        user_id=user_id, quiz_type=QuizType.CONCEPT, title="Quiz", questions=[MC_QUESTION]
    )

    feedback = await service.record_answer(user_id=user_id, quiz_id=quiz.id, answer_text="1")
    assert feedback.correct is True
    assert feedback.completed is True
    assert feedback.score == 1.0


async def test_answer_true_false(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = QuizService(session_factory, None)
    quiz = await service.create_quiz(
        user_id=user_id, quiz_type=QuizType.CONCEPT, title="Quiz", questions=[TF_QUESTION]
    )
    feedback = await service.record_answer(user_id=user_id, quiz_id=quiz.id, answer_text="falso")
    assert feedback.correct is True


async def test_quiz_multi_question_flow(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = QuizService(session_factory, None)
    quiz = await service.create_quiz(
        user_id=user_id,
        quiz_type=QuizType.CONCEPT,
        title="Quiz",
        questions=[MC_QUESTION, TF_QUESTION],
    )
    first = await service.record_answer(user_id=user_id, quiz_id=quiz.id, answer_text="1")
    assert first.completed is False
    assert first.next_prompt is not None

    second = await service.record_answer(user_id=user_id, quiz_id=quiz.id, answer_text="falso")
    assert second.completed is True
    assert second.score == 1.0


async def test_double_answer_is_idempotent(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = QuizService(session_factory, None)
    quiz = await service.create_quiz(
        user_id=user_id, quiz_type=QuizType.CONCEPT, title="Quiz", questions=[MC_QUESTION]
    )
    first = await service.record_answer(user_id=user_id, quiz_id=quiz.id, answer_text="1")
    assert first.completed is True
    # Volver a responder no debe duplicar la respuesta ni alterar la puntuación.
    second = await service.record_answer(user_id=user_id, quiz_id=quiz.id, answer_text="1")
    assert second.completed is True
    assert second.score == 1.0


async def test_generate_quiz_with_ai(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    ai = FakeAIService(
        ['{"questions": [{"type": "multiple_choice", "prompt": "Que es X?", "options": ["a", "b"], "correct_index": 0, "explanation": "..."}]}']
    )
    quiz = await QuizService(session_factory, ai).generate_quiz(
        user_id=user_id, quiz_type=QuizType.CONCEPT, title="T", context="contenido", n=1
    )
    assert quiz is not None
    assert quiz.status is QuizStatus.IN_PROGRESS


async def test_generate_quiz_without_ai_returns_none(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    quiz = await QuizService(session_factory, None).generate_quiz(
        user_id=user_id, quiz_type=QuizType.CONCEPT, title="T", context="x", n=1
    )
    assert quiz is None
