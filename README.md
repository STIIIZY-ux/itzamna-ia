# Itzamná IA

Asistente académico personal por Telegram. Esta es la **Etapa 3**: integración
con Google Calendar y sincronización inteligente.

## Stack

- Python 3.12+
- [FastAPI](https://fastapi.tiangolo.com/)
- [python-telegram-bot](https://python-telegram-bot.org/) (async)
- Pydantic + pydantic-settings
- SQLAlchemy 2.0 (async) + asyncpg
- Alembic (migraciones)
- httpx (cliente OAuth/API de Google, async)
- cryptography (cifrado Fernet de tokens)

## Estructura

```
asistente-ia/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI + ciclo de vida (bot + persistencia)
│   ├── config.py         # Settings desde variables de entorno
│   ├── security.py       # Redacción de secretos en logs/errores
│   ├── domain/
│   │   ├── enums.py          # Enums (estados, prioridad, fuente, ...)
│   │   ├── state_machine.py  # Transiciones válidas de estado de tarea
│   │   └── errors.py         # Errores de dominio
│   ├── db/
│   │   ├── base.py           # Base declarativa + convenciones
│   │   ├── engine.py         # Motor async + pool + factory de sesiones
│   │   ├── session.py        # session_scope (commit/rollback)
│   │   └── models/           # User, Subject, Task, TaskHistory, Commitment, Resource
│   ├── repositories/         # Acceso a datos (acotado por usuario)
│   ├── services/             # Casos de uso (tareas, sync, credenciales)
│   ├── integrations/
│   │   └── google/           # OAuth, cliente, normalizador, dedup, factory, CLI
│   └── bot/
│       ├── telegram_bot.py
│       └── handlers.py
├── migrations/           # Alembic (env.py + versions/0001, 0002)
├── tests/
├── alembic.ini
├── compose.yaml          # PostgreSQL para desarrollo
├── .env.example
├── .gitignore
├── .dockerignore
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── Dockerfile
└── README.md
```

## Instalación y ejecución local

### 1. Crear el entorno virtual

```bash
cd asistente-ia
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements-dev.txt
```

### 3. Levantar PostgreSQL (desarrollo)

```bash
docker compose up -d postgres
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y completa al menos:

- `TELEGRAM_BOT_TOKEN` — [@BotFather](https://t.me/BotFather).
- `TELEGRAM_ALLOWED_USER_ID` — [@userinfobot](https://t.me/userinfobot).
- `DATABASE_URL` — por defecto `postgresql+asyncpg://postgres:postgres@localhost:5432/itzamna`.

### 5. Ejecutar las migraciones

```bash
alembic upgrade head
```

### 6. Ejecutar el bot

```bash
uvicorn app.main:app --reload
# o, equivalentemente:
python -m app.main
```

## Migraciones

```bash
# aplicar a la última versión
alembic upgrade head

# ver la versión actual
alembic current

# crear una nueva migración (autogenerate)
alembic revision --autogenerate -m "descripción"

# revertir
alembic downgrade -1
```

## Tests

```bash
pytest
```

Los tests de persistencia levantan un cluster PostgreSQL **temporal y real**
(no simulado) usando `initdb`/`pg_ctl` disponibles en el host, ejecutan las
migraciones y corren contra él. Si `initdb`/`pg_ctl` no están en el `PATH`,
esos tests se omiten automáticamente.

## Docker

```bash
# PostgreSQL de desarrollo
docker compose up -d postgres

# Imagen de la aplicación
docker build -t itzamna-ia .
docker run --rm -p 8080:8080 --env-file .env itzamna-ia
```

Para producción se usará el modo webhook (`USE_WEBHOOK=true`, `WEBHOOK_URL` y
`TELEGRAM_WEBHOOK_SECRET`), ya preparado en `app/main.py`.

## Google Calendar

### Autorización OAuth (una sola vez)

1. Crea credenciales OAuth en [Google Cloud Console](https://console.cloud.google.com)
   (aplicación tipo "Web/Desktop"), con el scope
   `https://www.googleapis.com/auth/calendar.events.readonly` (solo lectura).
2. Define `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REDIRECT_URI`
   (p. ej. `http://localhost`) en `.env`.
3. Genera la clave de cifrado:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   y asígnala a `GOOGLE_TOKEN_ENCRYPTION_KEY` en `.env`.
4. Ejecuta el flujo de autorización:

   ```bash
   python -m app.integrations.google.authorize
   ```

   Pega la URL en el navegador, autoriza y pega el código devuelto. Los tokens
   se guardan **cifrados** (Fernet) en PostgreSQL.

### Sincronizar

- Desde Telegram: envía `/sync`.
- Desde código: `CalendarSyncService.sync(user_id)` (reutilizable, no ligado a
  Telegram).

La sincronización es **idempotente**, consolida duplicados, actualiza eventos
modificados y marca (sin borrar) los eventos eliminados. Se usa una ventana de
`GOOGLE_SYNC_TIME_WINDOW_DAYS` días (por defecto 120) con sincronización
completa (documentada; la incremental se puede añadir más adelante).

## Comandos de Telegram
- `/start` — saludo.
- `/sync` — sincronizar Google Calendar.
- `/next` — acción principal recomendada (planner determinista).
- `/estado` — resumen: pendientes, siguiente tarea, riesgo, compromiso activo.
- `/empiezo [task_id]` — registrar un compromiso (accountability).
- `/silencio [minutos]` — pausar notificaciones; `/silencio off` para reanudar.
- `/modo tryhard|guerra|silencio` — cambiar el modo.
- `/concepto` `/tip` `/dato` `/explica` `/pregunta` `/recomienda` — tutor académico.
- `/panic` o `/emergency` — modo de emergencia (plan de rescate por fases).

## Planner / Scheduler / Accountability

- El **planner** es determinista (sin IA): ordena por `prioridad` y `urgencia`
  (tiempo restante vs. estimación). Usa `FALLBACK_ESTIMATE_MINUTES=60` cuando no
  hay `estimated_minutes` (fallback explícito, no una estimación aprendida).
- El **scheduler** es persistente (PostgreSQL): los recordatorios sobreviven
  reinicios. Cada job tiene un `dedup_key` único que evita duplicados, y el
  estado `pending/claimed/sent` permite recuperar jobs tras un reinicio.
- El **accountability** (modo `tryhard` por defecto) mantiene un estado por
  tarea (`pending_reminder → committed → awaiting_evidence → completed`),
  registra compromisos y limita las insistencias por horario activo y por día.
  `guerra` está preparado (intervalos más cortos) y `silencio`/pausa detienen
  las notificaciones sin borrar nada.

## Archivos / Evidencia
- Envía una **foto** (o una imagen como documento, o un PDF) y el bot la valida
  (magic bytes), la almacena y la asocia a la tarea correspondiente.
- **Asociación determinista**: se asocia a la tarea en `AWAITING_EVIDENCE` o a
  la del compromiso activo; si no hay una tarea clara, se guarda **sin asociar**
  (no se adivina).
- El estado inicial de la evidencia es `pending_analysis` (la **visión/IA es de
  la Etapa 6**); los PDF quedan como `received`. Nunca se marca como válida
  automáticamente.
- **Almacenamiento privado** en disco (`STORAGE_DIR`, por defecto `./data/files`),
  con nombres internos (UUID) — nunca el nombre original del usuario. No se
  guardan binarios en PostgreSQL ni se sirven archivos públicamente.
- **Límites**: `STORAGE_MAX_FILE_BYTES` (20 MB) y `STORAGE_MAX_EVIDENCE_PER_TASK`
  (10). La deduplicación usa `file_unique_id` (no se guarda dos veces el mismo
  archivo).

## IA (tutor + visión + emergencia)

- La IA es un **componente externo desacoplado** (`AIService`); el resto de la
  aplicación no depende de un proveedor concreto. Se configura por variables de
  entorno (`AI_ENABLED`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, ...).
- Si la IA está deshabilitada o falla, el sistema **degrada de forma determinista**
  (p. ej. el modo emergencia usa un plan por fases sin IA).
- **Tutor** (`/concepto`, `/tip`, `/dato`, `/explica`, `/pregunta`, `/recomienda`):
  usa solo el contexto necesario de la tarea y **no inventa** información.
- **Visión**: la evidencia en `pending_analysis` se analiza de forma **asíncrona**
  (vía el scheduler persistente) y se marca `valid` / `invalid` / `uncertain`.
  No se marca como válida automáticamente; el modelo no controla la aplicación.
- **Prompt injection**: todo el contenido de Calendar/PDF/fotos/usuario se trata
  como **datos no confiables** y se delimita explícitamente; el sistema nunca
  ejecuta instrucciones embebidas en esos datos.
- **Modo emergencia** (`/panic`, `/emergency`): plan de rescate por fases; si
  falta material, lo pide explícitamente en lugar de inventarlo.

## Learning Engine / Control de lectura

- **Conceptos, preguntas, quizzes, flashcards** persistentes, con **dominio (0–1)**,
  **repetición espaciada determinista** y **detección de conceptos débiles**.
- Comandos: `/quiz` (quiz sobre la tarea actual), `/repaso` (flashcards atrasadas
  y conceptos débiles), `/libro <título>` (registra un libro y procesa el PDF),
  `/control` (control de lectura del capítulo) y `/examen` (examen final).
- **Libros**: los PDFs se procesan de forma **local** (pypdf, costo $0), se
  detectan capítulos de forma determinista (sin inventar estructura) y su
  contenido se trata como **datos no confiables** (protección anti-injection).
- La generación y evaluación con IA usa `AIService` (Gemini por defecto vía
  `GEMINI_API_KEY`/`GEMINI_MODEL`); si la IA está desactivada, degrada de forma
  determinista.

## Health check

- `GET /health` (readiness) devuelve `200 {"status": "ok"}` solo si **el bot y la
  base de datos** están operativos; si no, `503`.
- `GET /health/live` (liveness) devuelve siempre `200 {"status": "alive"}` (el
  proceso está vivo).

## Inteligencia adaptativa y estadísticas

- **Estimaciones adaptativas**: se calcula la duración real desde el historial
  de estados y se ajustan las estimaciones (sin sobrescribir la original; se
  guarda `adjusted_estimated_minutes` + `estimate_basis`).
- **Academic Score** (0-100, determinista, no es calificación universitaria):
  puntualidad, completitud, dominio, quizzes y constancia.
- **Estadísticas** (totales/semanal/diario), **briefing diario** (`/resumen`),
  **auditoría semanal** (`/semana`), **detección de procrastinación** y
  **modo rescate** (ofrece, no se autoactiva).
- Comandos: `/stats`, `/resumen`, `/semana`, `/score`.

## Producción 24/7

- **Rate limiter de IA real** (ventana deslizante) y **caché de IA** (TTL):
  `AI_MAX_CALLS_PER_HOUR` y `AI_CACHE_TTL_SECONDS`. Los hits de caché no cuentan
  contra el límite.
- **Scheduler multi-instancia**: los jobs se reclaman con `FOR UPDATE SKIP
  LOCKED`, por lo que dos instancias no envían el mismo recordatorio. La
  sincronización usa `pg_advisory_xact_lock` por usuario.
- **Webhook** protegido con `X-Telegram-Bot-Api-Secret-Token` (secreto
  obligatorio en producción).
- **Documentación**: `DOCS_ENABLED=false` oculta `/docs`, `/redoc` y
  `/openapi.json`.
- **Almacenamiento**: `LocalFileStorage` es para **desarrollo**. En Cloud Run
  (efímero) hay que montar un volumen persistente o usar almacenamiento de
  objetos (GCS/S3) para que la evidencia sobreviva reinicios.
- **Backups**: `pg_dump` de PostgreSQL + copia del directorio `STORAGE_DIR`.
  Recuperación documentada en esta sección.
- **Retención**: `STORAGE_RETENTION_DAYS` (por defecto 180); política
  documentada, sin borrado automático de material académico activo.

## Seguridad

- Los secretos se leen exclusivamente de variables de entorno.
- `.env` está en `.gitignore`; usa `.env.example` como plantilla.
- El acceso está restringido a `TELEGRAM_ALLOWED_USER_ID`.
- No se imprimen secretos en logs: un filtro global redacta token, secreto del
  webhook, `DATABASE_URL`, `GOOGLE_CLIENT_SECRET` y la clave de cifrado en
  mensajes y tracebacks.
- Los refresh/access tokens de Google se almacenan **cifrados** (Fernet); nunca
  en texto plano ni en logs.
- El contenido de los eventos de Calendar se trata como **datos** (nunca como
  instrucciones a ejecutar).
- Todas las consultas de repositorios están **acotadas por usuario**
  (`user_id`), de modo que un usuario no puede acceder a datos de otro.
- El webhook valida `X-Telegram-Bot-Api-Secret-Token` y exige
  `TELEGRAM_WEBHOOK_SECRET` cuando `USE_WEBHOOK=true`.

## Costo

El stack es de **costo $0** para un único usuario: PostgreSQL local o en el
nivel gratuito de cualquier nube, bot en polling y contenedor en el nivel
gratuito de Cloud Run (o una VPS mínima). No se usa ningún servicio administrado
de pago.

Componentes que **pueden** generar costo al superar el free tier:
- **Gemini** (llamadas de IA) — controlado por `AI_MAX_CALLS_PER_HOUR` y caché.
- **Cloud Run** (CPU/memoria por instancia) — 1 instancia en free tier.
- **PostgreSQL administrado** (si no se usa el free tier o un contenedor propio).
- **Almacenamiento** (si se usa GCS/S3 para evidencia en producción).

Para un solo usuario, todo permanece en los niveles gratuitos razonables.

## Preparación para GitHub (sin push todavía)

Antes de subir, verificar que NO se suba: `.env`, `GEMINI_API_KEY`/`AI_API_KEY`,
`GOOGLE_CLIENT_SECRET`, `DATABASE_URL`, tokens/refresh tokens, `data/` (archivos
de evidencia/libros), logs, y la base de datos. `.gitignore` y `.dockerignore`
ya cubren estos casos; revisar antes del primer commit.
