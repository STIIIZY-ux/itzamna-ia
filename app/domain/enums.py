"""Enums de dominio de Itzamná IA."""

from enum import Enum


class TaskStatus(str, Enum):
    """Estado de una tarea.

    El orden de los valores no implica un flujo lineal; las transiciones
    válidas se definen en :mod:`app.domain.state_machine`.
    """

    PENDIENTE = "pendiente"
    NOTIFICADA = "notificada"
    COMPROMISO = "compromiso"
    INICIADA = "iniciada"
    EN_PROGRESO = "en_progreso"
    TERMINADA = "terminada"
    ENTREGADA = "entregada"
    BLOQUEADA = "bloqueada"


class TaskPriority(str, Enum):
    """Prioridad de una tarea."""

    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    URGENTE = "urgente"


class TaskSource(str, Enum):
    """Origen de una tarea.

    Permite asociar una tarea a una fuente externa (p. ej. Google Calendar)
    sin implementar todavía la integración.
    """

    MANUAL = "manual"
    GOOGLE_CALENDAR = "google_calendar"


class CommitmentStatus(str, Enum):
    """Estado de un compromiso (accountability)."""

    ACTIVO = "activo"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"


class ResourceType(str, Enum):
    """Tipo de recurso asociado a una tarea."""

    PDF = "pdf"
    DOCUMENTO = "documento"
    IMAGEN = "imagen"
    ENLACE = "enlace"
    MATERIAL = "material"
    EVIDENCIA = "evidencia"
    ENTREGABLE = "entregable"
    OTRO = "otro"


class ResourceStatus(str, Enum):
    """Estado de procesamiento de un recurso/evidencia."""

    RECEIVED = "received"
    PENDING_ANALYSIS = "pending_analysis"
    VALID = "valid"
    INVALID = "invalid"
    UNCERTAIN = "uncertain"


class HistoryEventType(str, Enum):
    """Tipo de evento registrado en el historial de una tarea."""

    CREADA = "creada"
    ESTADO_CAMBIADO = "estado_cambiado"
    PRIORIDAD_CAMBIADA = "prioridad_cambiada"
    FECHA_CAMBIADA = "fecha_cambiada"
    ACTUALIZADA = "actualizada"
    REMOVIDA_DE_FUENTE = "removida_de_fuente"
    DUPLICADO_CONSOLIDADO = "duplicado_consolidado"
    OTRO = "otro"


class RiskLevel(str, Enum):
    """Nivel de riesgo de una tarea (determinista)."""

    NORMAL = "normal"
    ATENCION = "atencion"
    RIESGO = "riesgo"
    CRITICO = "critico"


class AccountabilityState(str, Enum):
    """Estado del flujo de accountability de una tarea."""

    PENDING_REMINDER = "pending_reminder"
    REMINDER_SENT = "reminder_sent"
    AWAITING_COMMITMENT = "awaiting_commitment"
    COMMITTED = "committed"
    AWAITING_EVIDENCE = "awaiting_evidence"
    COMPLETED = "completed"


class AccountabilityMode(str, Enum):
    """Modo de accountability."""

    TRYHARD = "tryhard"
    GUERRA = "guerra"
    SILENCIO = "silencio"


class JobKind(str, Enum):
    """Tipo de trabajo programado en el scheduler."""

    START_REMINDER = "start_reminder"
    DUE_REMINDER = "due_reminder"
    NUDGE = "nudge"
    EVIDENCE_REQUEST = "evidence_request"
    ANALYZE_EVIDENCE = "analyze_evidence"


class JobStatus(str, Enum):
    """Estado de un trabajo programado."""

    PENDING = "pending"
    CLAIMED = "claimed"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QuestionType(str, Enum):
    """Tipo de pregunta académica."""

    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    OPEN_ANSWER = "open_answer"
    EXERCISE = "exercise"


class QuizType(str, Enum):
    """Tipo de quiz."""

    TASK = "task"
    SUBJECT = "subject"
    CONCEPT = "concept"
    CHAPTER = "chapter"
    CUMULATIVE = "cumulative"
    FINAL = "final"


class QuizStatus(str, Enum):
    """Estado de un quiz."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class BookStatus(str, Enum):
    """Estado de procesamiento de un libro."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ChapterStatus(str, Enum):
    """Estado de lectura de un capítulo."""

    PENDIENTE = "pendiente"
    EN_LECTURA = "en_lectura"
    LEIDO = "leido"
    CONTROL_PENDIENTE = "control_pendiente"
    CONTROL_COMPLETADO = "control_completado"
    REPASO = "repaso"


class FlashcardStatus(str, Enum):
    """Estado de una flashcard."""

    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
