"""Manejadores de mensajes del bot de Telegram."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import get_settings
from app.security import redact_exception

logger = logging.getLogger(__name__)

GREETING = "Hola. Estoy listo para ayudarte."
NOT_AUTHORIZED = "No estás autorizado para usar este bot."


def is_user_authorized(user_id: int | None) -> bool:
    """Indica si un ``user_id`` coincide con el usuario permitido."""
    settings = get_settings()
    return user_id is not None and user_id == settings.telegram_allowed_user_id


def is_authorized(update: Update) -> bool:
    """Comprueba si el remitente de una ``Update`` está autorizado."""
    user = update.effective_user
    return is_user_authorized(user.id if user is not None else None)


def build_reply(text: str | None) -> str:
    """Construye la respuesta a un mensaje de texto."""
    if not text:
        return GREETING
    if text.strip().lower() in {"hola", "hola!", "hola.", "hi", "hello"}:
        return GREETING
    return f"Recibí tu mensaje: {text}"


async def _reject(update: Update) -> None:
    logger.warning("Intento de acceso no autorizado.")
    if update.message is not None:
        await update.message.reply_text(NOT_AUTHORIZED)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None:
        return
    user = update.effective_user
    if user is not None and user.first_name:
        await update.message.reply_text(f"Hola, {user.first_name}. Estoy listo para ayudarte.")
    else:
        await update.message.reply_text(GREETING)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None:
        return
    session_factory = _session_factory(context)
    if session_factory is not None and update.effective_user is not None:
        try:
            from app.db.session import session_scope
            from app.repositories.learning import QuizRepository
            from app.services.learning.quizzes import QuizService

            user = await _resolve_user(session_factory, update)
            async with session_scope(session_factory) as session:
                active = await QuizRepository(session).get_active(user_id=user.id)
            if active is not None:
                ai = context.bot_data.get("ai_service")
                feedback = await QuizService(session_factory, ai).record_answer(
                    user_id=user.id, quiz_id=active.id, answer_text=update.message.text or ""
                )
                await _reply_quiz_feedback(update, feedback)
                return
        except Exception as exc:  # noqa: BLE001
            logger.error("Error en respuesta de quiz:\n%s", redact_exception(exc))

    reply = build_reply(update.message.text)
    await update.message.reply_text(reply)


async def _reply_quiz_feedback(update: Update, feedback) -> None:
    if feedback.completed:
        text = (
            f"🎉 Quiz completado.\nResultado: {feedback.feedback}\n"
            f"Puntuación: {round((feedback.score or 0) * 100)}%"
        )
    else:
        text = feedback.feedback
        if feedback.explanation:
            text += f"\n💡 {feedback.explanation}"
        if feedback.next_prompt:
            text += f"\n\n📝 {feedback.next_prompt}"
    if update.message is not None:
        await update.message.reply_text(text)


async def handle_application_error(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Error handler global: registra el error sin revelar secretos ni romper el bot."""
    del update
    error = context.error
    if error is None:
        logger.error("Error desconocido al procesar una actualización de Telegram")
        return
    logger.error(
        "Error al procesar una actualización de Telegram:\n%s",
        redact_exception(error),
    )


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispara una sincronización manual con Google Calendar."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return

    session_factory = context.bot_data.get("session_factory")
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return

    try:
        from app.integrations.google.factory import build_stack, is_configured
        from app.services.users import UserService

        if not is_configured():
            await update.message.reply_text("Google Calendar no está configurado.")
            return

        user = await UserService(session_factory).get_or_create_by_telegram(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
        )
        result = await build_stack(session_factory).sync.sync(user.id)
        await update.message.reply_text(
            "Sincronización completada:\n"
            f"• nuevas: {result.created}\n"
            f"• actualizadas: {result.updated}\n"
            f"• sin cambios: {result.unchanged}\n"
            f"• duplicados consolidados: {result.consolidated}\n"
            f"• removidas: {result.removed}\n"
            f"• omitidas: {result.skipped}"
        )
    except Exception as exc:  # noqa: BLE001 - se degrada de forma controlada
        logger.error("Error al sincronizar Google Calendar:\n%s", redact_exception(exc))
        await update.message.reply_text("No se pudo sincronizar Google Calendar.")


def _session_factory(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("session_factory")


async def _resolve_user(session_factory, update: Update):
    from app.services.users import UserService

    if update.effective_user is None:
        raise RuntimeError("update sin usuario")
    return await UserService(session_factory).get_or_create_by_telegram(
        telegram_id=update.effective_user.id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
    )


async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Devuelve la acción principal recomendada por el planner."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.scheduler.messages import format_due
        from app.services.planning import PlanningService

        user = await _resolve_user(session_factory, update)
        recommendation = await PlanningService(session_factory).next_recommendation(user.id)
        if recommendation is None:
            await update.message.reply_text("No tienes tareas pendientes. 🎉")
            return
        task = recommendation.task
        due = format_due(task.due_at, task.timezone or get_settings().user_timezone)
        estimated = (
            f"{task.estimated_minutes // 60} h"
            if task.estimated_minutes and task.estimated_minutes >= 60
            else (f"{task.estimated_minutes} min" if task.estimated_minutes else "sin estimación")
        )
        subject = f" — {task.subject}" if task.subject else ""
        await update.message.reply_text(
            f"🎯 Ahora:\n{task.title}{subject}\n\n"
            f"Vence: {due} ({recommendation.urgency})\n"
            f"Estimación: {estimated}\n\n"
            f"Empieza con: {recommendation.first_step}"
        )
    except Exception as exc:  # noqa: BLE001 - se degrada de forma controlada
        logger.error("Error en /next:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude calcular la siguiente acción.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el estado actual del usuario."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.scheduler.messages import format_due
        from app.services.planning import PlanningService

        user = await _resolve_user(session_factory, update)
        summary = await PlanningService(session_factory).status_summary(user.id)
        risk = summary.next_risk.value if summary.next_risk else "—"
        due = format_due(summary.next_due, get_settings().user_timezone) if summary.next_due else "—"
        commitment = summary.active_commitment_title or "ninguno"
        await update.message.reply_text(
            "📋 Estado:\n"
            f"• Pendientes: {summary.pending_count}\n"
            f"• Siguiente: {summary.next_title or '—'}\n"
            f"• Vence: {due}\n"
            f"• Riesgo: {risk}\n"
            f"• Compromiso activo: {commitment}\n"
            f"• Candidatos a rescate: {summary.rescue_candidates}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /estado:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude obtener el estado.")


async def silence_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pausa o reanuda las notificaciones: /silencio [minutos] | /silencio off."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.services.notification_preferences import NotificationPreferencesService

        user = await _resolve_user(session_factory, update)
        service = NotificationPreferencesService(session_factory)
        args = context.args or []
        if args and args[0].strip().lower() in ("off", "0"):
            await service.resume(user.id)
            await update.message.reply_text("Silencio desactivado. 🔔")
            return
        minutes = int(args[0]) if args and args[0].isdigit() else 60
        await service.pause(user.id, minutes=minutes)
        await update.message.reply_text(f"Silencio activado por {minutes} minutos. 🤫")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /silencio:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude cambiar el silencio.")


async def commit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra un compromiso: /empiezo [task_id]."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.domain.enums import TaskStatus
        from app.domain.errors import InvalidStateTransitionError
        from app.services.accountability import AccountabilityService
        from app.services.planning import PlanningService
        from app.services.tasks import TaskService

        user = await _resolve_user(session_factory, update)
        args = context.args or []
        task_id = int(args[0]) if args and args[0].isdigit() else None
        if task_id is None:
            recommendation = await PlanningService(session_factory).next_recommendation(user.id)
            if recommendation is None:
                await update.message.reply_text("No tienes tareas pendientes.")
                return
            task_id = recommendation.task.id

        await AccountabilityService(session_factory).record_commitment(
            user_id=user.id, task_id=task_id
        )
        task = await TaskService(session_factory).get_task(user_id=user.id, task_id=task_id)
        try:
            await TaskService(session_factory).change_status(
                user_id=user.id, task_id=task_id, new_status=TaskStatus.COMPROMISO
            )
        except InvalidStateTransitionError:
            pass  # la tarea ya está más avanzada
        await update.message.reply_text(f"✅ Compromiso registrado: {task.title}")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /empiezo:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude registrar el compromiso.")


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cambia el modo de accountability: /modo tryhard|guerra|silencio."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.domain.enums import AccountabilityMode
        from app.services.notification_preferences import NotificationPreferencesService

        user = await _resolve_user(session_factory, update)
        args = context.args or []
        if not args:
            await update.message.reply_text("Uso: /modo tryhard|guerra|silencio")
            return
        try:
            mode = AccountabilityMode(args[0].strip().lower())
        except ValueError:
            await update.message.reply_text("Modo inválido. Usa tryhard, guerra o silencio.")
            return
        await NotificationPreferencesService(session_factory).set_mode(user.id, mode)
        await update.message.reply_text(f"Modo: {mode.value}")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /modo:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude cambiar el modo.")


async def _store_upload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session_factory,
    user_id: int,
    *,
    file_id: str,
    file_unique_id: str,
    name: str | None,
    telegram_size: int | None,
):
    """Almacena un archivo subido. Devuelve ``StoredFile`` o ``None`` (ya respondió)."""
    settings = get_settings()
    if update.message is None:
        return None

    if telegram_size is not None and telegram_size > settings.storage_max_file_bytes:
        await update.message.reply_text("El archivo es demasiado grande.")
        return None

    try:
        tg_file = await context.bot.get_file(file_id)
        data = bytes(await tg_file.download_as_bytearray())
    except Exception as exc:  # noqa: BLE001
        logger.error("Error descargando archivo de Telegram:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude descargar el archivo.")
        return None

    from app.services.evidence import (
        EvidenceService,
        FileTooLargeError,
        FileValidationError,
        TooManyEvidenceError,
    )
    from app.storage.local import LocalFileStorage

    storage = context.bot_data.get("storage") or LocalFileStorage(settings.storage_dir)
    scheduler = context.bot_data.get("scheduler")
    service = EvidenceService(
        session_factory,
        storage,
        max_file_bytes=settings.storage_max_file_bytes,
        max_evidence_per_task=settings.storage_max_evidence_per_task,
        scheduler=scheduler,
    )

    task_id = await service.resolve_task(user_id)
    try:
        stored = await service.store_upload(
            user_id=user_id,
            task_id=task_id,
            file_unique_id=file_unique_id,
            file_id=file_id,
            name=name,
            data=data,
            metadata={
                "message_id": update.message.message_id,
                "telegram_size": telegram_size,
            },
        )
    except FileValidationError:
        await update.message.reply_text("Formato no soportado. Envía una imagen o un PDF.")
        return None
    except FileTooLargeError:
        await update.message.reply_text("El archivo es demasiado grande.")
        return None
    except TooManyEvidenceError:
        await update.message.reply_text("Ya tienes muchas evidencias para esta tarea.")
        return None

    if not stored.created:
        await update.message.reply_text("Ya recibí este archivo antes.")
        return None

    return stored


async def _attach_pending_book(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session_factory, user_id: int, stored
):
    """Si hay un libro pendiente, asocia el PDF recién subido y lo procesa.

    Devuelve ``True`` si se procesó un libro (ya respondió), ``False`` en caso
    contrario.
    """
    from app.domain.enums import ResourceType
    from app.services.books import BookService

    resource = stored.resource
    if resource.resource_type is not ResourceType.PDF:
        return False
    storage = context.bot_data.get("storage")
    if storage is None:
        return False
    book = await BookService(session_factory, storage).attach_pending(
        user_id=user_id, resource=resource
    )
    if book is not None and update.message is not None:
        if book.num_chapters:
            await update.message.reply_text(f"📖 Libro procesado: {book.num_chapters} capítulos.")
        else:
            await update.message.reply_text(
                "📖 Libro procesado, pero no se detectó estructura de capítulos."
            )
        return True
    return False


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe una fotografía de evidencia."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        if not update.message.photo:
            return
        user = await _resolve_user(session_factory, update)
        photo = update.message.photo[-1]  # mayor resolución
        stored = await _store_upload(
            update,
            context,
            session_factory,
            user.id,
            file_id=photo.file_id,
            file_unique_id=photo.file_unique_id,
            name=None,
            telegram_size=photo.file_size,
        )
        if stored is not None and update.message is not None:
            if stored.resource.task_id is None:
                await update.message.reply_text(
                    "📸 Evidencia recibida y guardada, pero no identifiqué la tarea. "
                    "Usa /empiezo para asociarla."
                )
            else:
                await update.message.reply_text("📸 Evidencia recibida y guardada. Queda pendiente de análisis.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en handle_photo:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude guardar la evidencia.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe un documento (imagen o PDF) de evidencia/material."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        document = update.message.document
        if document is None:
            return
        user = await _resolve_user(session_factory, update)
        stored = await _store_upload(
            update,
            context,
            session_factory,
            user.id,
            file_id=document.file_id,
            file_unique_id=document.file_unique_id,
            name=document.file_name,
            telegram_size=document.file_size,
        )
        if stored is None:
            return
        book_processed = await _attach_pending_book(
            update, context, session_factory, user.id, stored
        )
        if not book_processed and update.message is not None:
            await update.message.reply_text("📄 Documento recibido.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en handle_document:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude guardar el archivo.")


async def _task_context(session_factory, user_id: int) -> dict | None:
    """Resuelve el contexto de la tarea actual (planner + DB)."""
    from app.db.session import session_scope
    from app.repositories.resources import ResourceRepository
    from app.repositories.tasks import TaskRepository
    from app.scheduler.messages import format_due
    from app.services.planning import PlanningService

    recommendation = await PlanningService(session_factory).next_recommendation(user_id)
    if recommendation is None:
        return None
    task_id = recommendation.task.id
    async with session_scope(session_factory) as session:
        task = await TaskRepository(session).get(user_id=user_id, task_id=task_id)
        resources = await ResourceRepository(session).list_for_task(task_id) if task else []
    return {
        "title": recommendation.task.title,
        "subject": recommendation.task.subject,
        "instructions": task.instructions if task else None,
        "description": task.description if task else None,
        "resources": [r.uri or r.name for r in resources if r.uri or r.name],
        "due": format_due(
            recommendation.task.due_at,
            recommendation.task.timezone or get_settings().user_timezone,
        ),
    }


async def tutor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tutor académico: /concepto /tip /dato /explica /pregunta /recomienda."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        ai = context.bot_data.get("ai_service")
        if ai is None:
            await update.message.reply_text("La IA no está disponible.")
            return
        from app.services.tutor import TutorService

        kind = (update.message.text or "/concepto").split()[0].lstrip("/")
        user = await _resolve_user(session_factory, update)
        ctx = await _task_context(session_factory, user.id)
        if ctx is None:
            await update.message.reply_text("No tienes tareas pendientes.")
            return
        content = await TutorService(ai).generate(kind=kind, **ctx)
        await update.message.reply_text(content)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en tutor:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude generar la respuesta.")


async def panic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Modo emergencia: /panic o /emergency."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.services.emergency import EmergencyService

        ai = context.bot_data.get("ai_service")
        user = await _resolve_user(session_factory, update)
        plan = await EmergencyService(session_factory, ai).build_plan(user.id)
        await update.message.reply_text(plan)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en modo emergencia:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude preparar el plan de emergencia.")


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Repaso de flashcards atrasadas y conceptos débiles: /repaso."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.services.learning.review import ReviewService

        user = await _resolve_user(session_factory, update)
        items = await ReviewService(session_factory).pick(user_id=user.id, limit=5)
        if not items:
            await update.message.reply_text("No hay nada que repasar ahora. 🎉")
            return
        lines = ["📚 Repaso:"]
        for item in items:
            icon = "🃏" if item.kind == "flashcard" else "🧠"
            lines.append(f"{icon} {item.front}\n   → {item.back}")
        await update.message.reply_text("\n\n".join(lines))
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /repaso:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude preparar el repaso.")


async def _ask_first_question(session_factory, quiz) -> str | None:
    from app.db.session import session_scope
    from app.repositories.learning import QuizRepository

    async with session_scope(session_factory) as session:
        questions = await QuizRepository(session).list_questions(quiz_id=quiz.id)
    return questions[0].prompt if questions else None


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera un quiz sobre la tarea actual: /quiz."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        ai = context.bot_data.get("ai_service")
        if ai is None:
            await update.message.reply_text("La IA no está disponible.")
            return
        from app.domain.enums import QuizType
        from app.services.learning.quizzes import QuizService

        user = await _resolve_user(session_factory, update)
        ctx = await _task_context(session_factory, user.id)
        if ctx is None:
            await update.message.reply_text("No tienes tareas pendientes.")
            return
        context_text = (
            f"Actividad: {ctx['title']}\n"
            f"Instrucciones: {ctx['instructions'] or '—'}\n"
            f"Descripción: {ctx['description'] or '—'}"
        )
        quiz = await QuizService(session_factory, ai).generate_quiz(
            user_id=user.id,
            quiz_type=QuizType.TASK,
            title=f"Quiz: {ctx['title']}",
            context=context_text,
            n=3,
        )
        if quiz is None:
            await update.message.reply_text("No pude generar el quiz.")
            return
        first = await _ask_first_question(session_factory, quiz)
        await update.message.reply_text(f"📝 {quiz.title}\n\n1. {first}")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /quiz:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude generar el quiz.")


async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra un libro pendiente: /libro <título>."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.services.books import BookService
        from app.storage.local import LocalFileStorage

        user = await _resolve_user(session_factory, update)
        args = context.args or []
        title = " ".join(args).strip() or "Libro sin título"
        storage = context.bot_data.get("storage") or LocalFileStorage(get_settings().storage_dir)
        await BookService(session_factory, storage).register(user_id=user.id, title=title)
        await update.message.reply_text(f"📖 Libro registrado: {title}\nEnvía el PDF para procesarlo.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /libro:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude registrar el libro.")


async def _latest_book(session_factory, user_id: int):
    from app.db.session import session_scope
    from app.repositories.learning import BookRepository

    async with session_scope(session_factory) as session:
        books = await BookRepository(session).list(user_id=user_id)
    return books[0] if books else None


async def control_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Control de lectura del capítulo actual: /control."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        ai = context.bot_data.get("ai_service")
        if ai is None:
            await update.message.reply_text("La IA no está disponible.")
            return
        from app.services.reading import ReadingControlService

        user = await _resolve_user(session_factory, update)
        book = await _latest_book(session_factory, user.id)
        if book is None:
            await update.message.reply_text("No tienes libros. Usa /libro <título> y envía el PDF.")
            return
        quiz = await ReadingControlService(session_factory, ai).chapter_control(
            user_id=user.id, book_id=book.id
        )
        if quiz is None:
            await update.message.reply_text("No pude generar el control de lectura.")
            return
        first = await _ask_first_question(session_factory, quiz)
        await update.message.reply_text(f"📖 CONTROL DE LECTURA\n{quiz.title}\n\n1. {first}")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /control:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude generar el control.")


async def exam_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Examen final del libro actual: /examen."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        ai = context.bot_data.get("ai_service")
        if ai is None:
            await update.message.reply_text("La IA no está disponible.")
            return
        from app.services.reading import ReadingControlService

        user = await _resolve_user(session_factory, update)
        book = await _latest_book(session_factory, user.id)
        if book is None:
            await update.message.reply_text("No tienes libros. Usa /libro <título> y envía el PDF.")
            return
        quiz = await ReadingControlService(session_factory, ai).final_exam(
            user_id=user.id, book_id=book.id
        )
        if quiz is None:
            await update.message.reply_text("No pude generar el examen final.")
            return
        first = await _ask_first_question(session_factory, quiz)
        await update.message.reply_text(f"📖 EXAMEN FINAL\n\n1. {first}")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /examen:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude generar el examen.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Estadísticas históricas: /stats."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.services.statistics import StatisticsService

        user = await _resolve_user(session_factory, update)
        stats = await StatisticsService(session_factory).totals(user.id)
        mastery = round(stats.avg_mastery, 2) if stats.avg_mastery is not None else "—"
        quiz = round(stats.quiz_avg * 100) if stats.quiz_avg is not None else "—"
        await update.message.reply_text(
            "📊 Estadísticas:\n"
            f"• Tareas: {stats.tasks_completed} completadas / {stats.tasks_total} totales\n"
            f"• A tiempo: {stats.on_time}\n"
            f"• Atrasadas: {stats.tasks_overdue}\n"
            f"• Quizzes: {stats.quizzes_taken} (promedio {quiz}%)\n"
            f"• Dominio medio: {mastery}\n"
            f"• Conceptos débiles: {stats.weak_concepts}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /stats:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude calcular las estadísticas.")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resumen diario: /resumen."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.services.briefing import BriefingService

        user = await _resolve_user(session_factory, update)
        ai = context.bot_data.get("ai_service")
        text = await BriefingService(session_factory, ai, get_settings().user_timezone).daily_briefing(
            user.id
        )
        await update.message.reply_text(text)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /resumen:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude generar el resumen.")


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auditoría semanal: /semana."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.services.briefing import BriefingService

        user = await _resolve_user(session_factory, update)
        ai = context.bot_data.get("ai_service")
        text = await BriefingService(session_factory, ai, get_settings().user_timezone).weekly_audit(
            user.id
        )
        await update.message.reply_text(text)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /semana:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude generar la auditoría.")


async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Academic Score interno: /score."""
    if not is_authorized(update):
        await _reject(update)
        return
    if update.message is None or update.effective_user is None:
        return
    session_factory = _session_factory(context)
    if session_factory is None:
        await update.message.reply_text("La base de datos no está disponible.")
        return
    try:
        from app.services.score import AcademicScoreService

        user = await _resolve_user(session_factory, update)
        result = await AcademicScoreService(session_factory).compute(user.id)
        breakdown = "\n".join(f"• {k}: {v}%" for k, v in result.breakdown.items())
        await update.message.reply_text(f"🎓 Academic Score: {result.score}/100\n\n{breakdown}")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en /score:\n%s", redact_exception(exc))
        await update.message.reply_text("No pude calcular el Academic Score.")


def register_handlers(application: Application) -> None:
    """Registra los manejadores en la ``Application``."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("sync", sync_command))
    application.add_handler(CommandHandler("next", next_command))
    application.add_handler(CommandHandler("estado", status_command))
    application.add_handler(CommandHandler("silencio", silence_command))
    application.add_handler(CommandHandler("empiezo", commit_command))
    application.add_handler(CommandHandler("modo", mode_command))
    application.add_handler(CommandHandler("panic", panic_command))
    application.add_handler(CommandHandler("emergency", panic_command))
    application.add_handler(CommandHandler("repaso", review_command))
    application.add_handler(CommandHandler("quiz", quiz_command))
    application.add_handler(CommandHandler("libro", book_command))
    application.add_handler(CommandHandler("control", control_command))
    application.add_handler(CommandHandler("examen", exam_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("resumen", resume_command))
    application.add_handler(CommandHandler("semana", week_command))
    application.add_handler(CommandHandler("score", score_command))
    for command in ("concepto", "tip", "dato", "explica", "pregunta", "recomienda"):
        application.add_handler(CommandHandler(command, tutor_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(
        MessageHandler(filters.Document.IMAGE | filters.Document.PDF, handle_document)
    )
    application.add_error_handler(handle_application_error)
