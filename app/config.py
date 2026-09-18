"""Configuración de la aplicación cargada desde variables de entorno."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central del asistente.

    Los valores se leen de variables de entorno y, opcionalmente, de un
    archivo ``.env``. Los secretos nunca se escriben en el código.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: str = Field(..., min_length=1, description="Token del bot")
    telegram_allowed_user_id: int = Field(..., gt=0, description="ID autorizado")
    environment: str = Field(default="development", description="Entorno de ejecución")
    use_webhook: bool = Field(default=False, description="Usar webhook en vez de polling")
    webhook_url: str | None = Field(default=None, description="URL pública del webhook")
    telegram_webhook_secret: str | None = Field(
        default=None, description="Secreto para validar el webhook de Telegram"
    )
    port: int = Field(default=8080, ge=1, le=65535, description="Puerto del servidor web")
    database_url: str | None = Field(
        default=None,
        description="URL async de PostgreSQL (postgresql+asyncpg://...). Si es None, la persistencia se omite.",
    )
    database_pool_size: int = Field(default=5, ge=1, le=50, description="Tamaño del pool")
    database_max_overflow: int = Field(
        default=10, ge=0, le=100, description="Conexiones extra del pool"
    )
    database_echo: bool = Field(default=False, description="Log SQL (solo desarrollo)")

    # --- Google Calendar ---
    google_client_id: str | None = Field(default=None, description="Client ID de OAuth 2.0")
    google_client_secret: str | None = Field(
        default=None, description="Client secret de OAuth 2.0 (secreto)"
    )
    google_redirect_uri: str | None = Field(
        default=None, description="Redirect URI configurada en Google Cloud Console"
    )
    google_token_encryption_key: str | None = Field(
        default=None,
        description="Clave Fernet (URL-safe base64) para cifrar refresh tokens en BD",
    )
    google_calendar_id: str = Field(
        default="primary", description="ID del calendario a sincronizar"
    )
    google_sync_time_window_days: int = Field(
        default=120, ge=1, le=730, description="Ventana (días) de eventos a sincronizar"
    )
    user_timezone: str = Field(
        default="America/Tijuana", description="Zona horaria del usuario (IANA)"
    )

    # --- Planner / Scheduler / Accountability ---
    accountability_mode: str = Field(
        default="tryhard", description="Modo por defecto: tryhard | guerra | silencio"
    )
    accountability_active_hour_start: int = Field(default=9, ge=0, le=23)
    accountability_active_hour_end: int = Field(default=21, ge=0, le=23)
    accountability_max_reminders_per_day: int = Field(default=5, ge=1, le=50)
    accountability_tryhard_interval_minutes: int = Field(default=120, ge=1, le=1440)
    accountability_guerra_interval_minutes: int = Field(default=30, ge=1, le=1440)
    scheduler_enabled: bool = Field(default=True, description="Activar el scheduler")
    scheduler_poll_interval_seconds: float = Field(default=30.0, ge=1.0, le=3600)
    scheduler_stale_claim_seconds: float = Field(default=300.0, ge=10.0)
    scheduler_claim_batch_size: int = Field(default=20, ge=1, le=500)

    # --- Archivos / Evidencia ---
    storage_dir: str = Field(
        default="./data/files", description="Directorio local de almacenamiento de archivos"
    )
    storage_max_file_bytes: int = Field(
        default=20 * 1024 * 1024, ge=1, description="Tamaño máximo por archivo (bytes)"
    )
    storage_max_evidence_per_task: int = Field(
        default=10, ge=1, le=100, description="Máximo de evidencias por tarea"
    )

    # --- IA ---
    ai_enabled: bool = Field(default=False, description="Activar IA")
    ai_api_key: str | None = Field(default=None, description="API key del proveedor (secreto)")
    ai_provider: str = Field(default="openai-compatible", description="Nombre del proveedor")
    ai_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        description="Endpoint base del proveedor (Gemini OpenAI-compatible por defecto)",
    )
    ai_model: str = Field(default="gemini-3.6-flash", description="Modelo a usar")
    ai_timeout_seconds: float = Field(default=60.0, ge=1.0, le=600)
    ai_max_retries: int = Field(default=2, ge=0, le=5)
    ai_max_tokens: int = Field(default=1024, ge=1, le=32000)
    ai_max_calls_per_hour: int = Field(default=200, ge=1, le=10000)
    ai_cache_ttl_seconds: float = Field(default=3600.0, ge=0.0, le=86400)
    # Alias de Gemini (compatibles con la documentación del usuario).
    gemini_api_key: str | None = Field(default=None, description="API key de Gemini (secreto)")
    gemini_model: str | None = Field(default=None, description="Modelo de Gemini")

    # --- Producción / despliegue ---
    docs_enabled: bool = Field(default=True, description="Exponer /docs /redoc /openapi.json")
    storage_retention_days: int = Field(default=180, ge=1, le=3650)

    @field_validator("telegram_bot_token")
    @classmethod
    def _validate_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN no puede estar vacío")
        if ":" not in token:
            raise ValueError("TELEGRAM_BOT_TOKEN no tiene un formato válido")
        return token

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() in {"development", "dev", "local"}


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia única (cacheada) de la configuración."""
    # Los valores se leen de variables de entorno/.env, no de argumentos.
    return Settings()  # type: ignore[call-arg]
