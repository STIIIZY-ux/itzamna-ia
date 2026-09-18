"""Punto de entrada: servidor FastAPI + bot de Telegram + persistencia."""

import logging
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from telegram import Update
from telegram.error import TelegramError

from app.ai.factory import build_ai_service
from app.bot.handlers import register_handlers
from app.bot.telegram_bot import build_application
from app.config import get_settings
from app.db.engine import dispose_engine, get_engine, get_session_factory
from app.scheduler.dispatch import make_dispatcher
from app.scheduler.runner import SchedulerRunner
from app.scheduler.service import SchedulerService
from app.security import install_secrets_filter, redact_exception
from app.services.evidence_analysis import make_evidence_dispatcher
from app.storage.local import LocalFileStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
install_secrets_filter()
logger = logging.getLogger(__name__)

WEBHOOK_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


async def _check_database_connection() -> None:
    """Verifica la conexión a PostgreSQL, lanzando si falla."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.bot_ready = False
    app.state.db_ready = False

    # --- Persistencia ---
    if settings.database_url:
        try:
            await _check_database_connection()
            app.state.db_ready = True
            logger.info("Base de datos PostgreSQL conectada")
        except Exception as exc:  # noqa: BLE001 - los drivers async lanzan varios tipos
            logger.error("No se pudo conectar a PostgreSQL:\n%s", redact_exception(exc))
    else:
        app.state.db_ready = True
        logger.warning("DATABASE_URL no configurado; la persistencia está deshabilitada")

    # --- Bot de Telegram ---
    application = build_application()
    if settings.database_url:
        factory = get_session_factory()
        application.bot_data["session_factory"] = factory
        application.bot_data["storage"] = LocalFileStorage(settings.storage_dir)
        application.bot_data["scheduler"] = SchedulerService(factory)
        application.bot_data["ai_service"] = build_ai_service(settings)
    register_handlers(application)
    app.state.telegram_application = application

    updater = application.updater
    initialized = False
    started = False
    webhook_configured = False
    polling_started = False

    try:
        if updater is None:
            raise RuntimeError("El Updater de Telegram no está disponible")

        if settings.use_webhook:
            if not settings.webhook_url:
                raise RuntimeError("WEBHOOK_URL es obligatorio cuando USE_WEBHOOK=true")
            if not settings.telegram_webhook_secret:
                raise RuntimeError(
                    "TELEGRAM_WEBHOOK_SECRET es obligatorio cuando USE_WEBHOOK=true"
                )

        await application.initialize()
        initialized = True
        await application.start()
        started = True

        if settings.use_webhook:
            await application.bot.set_webhook(
                url=settings.webhook_url,
                secret_token=settings.telegram_webhook_secret,
            )
            webhook_configured = True
            logger.info("Webhook configurado")
        else:
            await updater.start_polling()
            polling_started = True
            logger.info("Bot iniciado en modo polling")

        bot = await application.bot.get_me()
        logger.info("Bot @%s listo", bot.username)
        app.state.bot_ready = True
    except (TelegramError, RuntimeError) as exc:
        logger.error("No se pudo iniciar el bot de Telegram:\n%s", redact_exception(exc))

    # --- Scheduler persistente ---
    scheduler_runner: SchedulerRunner | None = None
    if settings.database_url and settings.scheduler_enabled and app.state.bot_ready:
        try:
            factory = get_session_factory()
            scheduler = SchedulerService(factory)
            storage = LocalFileStorage(settings.storage_dir)
            ai_service = build_ai_service(settings)

            async def send_message(chat_id: int, text: str) -> None:
                await application.bot.send_message(chat_id=chat_id, text=text)

            analyze_evidence = make_evidence_dispatcher(
                send_message, factory, storage, ai_service
            )
            dispatch = make_dispatcher(
                send_message, factory, settings.user_timezone, analyze_evidence
            )
            scheduler_runner = SchedulerRunner(
                scheduler=scheduler,
                dispatch=dispatch,
                poll_interval_seconds=settings.scheduler_poll_interval_seconds,
                stale_claim_seconds=settings.scheduler_stale_claim_seconds,
                claim_batch_size=settings.scheduler_claim_batch_size,
            )
            await scheduler_runner.start()
            app.state.scheduler_runner = scheduler_runner
            app.state.scheduler_ready = True
            logger.info("Scheduler iniciado")
        except Exception as exc:  # noqa: BLE001
            logger.error("No se pudo iniciar el scheduler:\n%s", redact_exception(exc))

    yield

    if scheduler_runner is not None:
        await scheduler_runner.stop()
        app.state.scheduler_ready = False
        logger.info("Scheduler detenido")

    try:
        if webhook_configured:
            await application.bot.delete_webhook()
        if polling_started and updater is not None:
            await updater.stop()
        if started:
            await application.stop()
        if initialized:
            await application.shutdown()
    except (TelegramError, RuntimeError) as exc:
        logger.error("Error al detener el bot de Telegram:\n%s", redact_exception(exc))
    finally:
        app.state.bot_ready = False
    logger.info("Bot detenido")

    # --- Cierre de persistencia ---
    try:
        await dispose_engine()
    except Exception as exc:  # noqa: BLE001 - cierre controlado del pool
        logger.error("Error al cerrar el pool de PostgreSQL:\n%s", redact_exception(exc))
    finally:
        app.state.db_ready = False


_DOCS_ENABLED = os.environ.get("DOCS_ENABLED", "true").strip().lower() not in {"false", "0", "no"}

app = FastAPI(
    title="Itzamná IA",
    lifespan=lifespan,
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)
app.state.bot_ready = False
app.state.db_ready = False
app.state.scheduler_ready = False


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    bot_ready = getattr(request.app.state, "bot_ready", False)
    db_ready = getattr(request.app.state, "db_ready", False)
    if bot_ready and db_ready:
        return JSONResponse(content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "unhealthy"})


@app.get("/health/live")
async def health_live() -> JSONResponse:
    return JSONResponse(content={"status": "alive"})


@app.post("/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    """Recibe actualizaciones cuando el bot opera en modo webhook."""
    settings = get_settings()
    if not settings.use_webhook:
        return JSONResponse(status_code=404, content={"detail": "Webhook no habilitado"})

    if not getattr(request.app.state, "bot_ready", False):
        return JSONResponse(status_code=503, content={"detail": "Bot no disponible"})

    secret = settings.telegram_webhook_secret
    if not secret:
        return JSONResponse(
            status_code=403, content={"detail": "Webhook mal configurado (sin secreto)"}
        )

    header = request.headers.get(WEBHOOK_SECRET_HEADER)
    if header is None or not secrets.compare_digest(header, secret):
        return JSONResponse(status_code=403, content={"detail": "Secreto del webhook inválido"})

    try:
        data = await request.json()
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Cuerpo JSON inválido"})

    if not isinstance(data, dict):
        return JSONResponse(status_code=400, content={"detail": "Payload inválido"})

    application = request.app.state.telegram_application
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return JSONResponse(content={"status": "ok"})


def run() -> None:
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    run()
