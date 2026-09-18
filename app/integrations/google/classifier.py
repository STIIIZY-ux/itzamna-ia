"""Clasificación heurística de eventos de Google Calendar.

Determina si un evento representa una tarea académica (entrega, examen, etc.)
o no (clase, reunión, evento personal). La clasificación es **conservadora**:
ante la duda, el evento NO se trata como tarea. Esta lógica es modular para
poder mejorarse en etapas posteriores sin IA.
"""

_TASK_KEYWORDS = (
    "entrega",
    "tarea",
    "examen",
    "parcial",
    "final",
    "quiz",
    "control de lectura",
    "lectura",
    "actividad",
    "práctica",
    "practica",
    "proyecto",
    "ensayo",
    "resumen",
    "exposición",
    "exposicion",
    "deadline",
    "taller",
    "laboratorio",
    "reporte",
    "investigación",
    "investigacion",
    "ejercicio",
    "problema",
    "portafolio",
)

_NON_TASK_KEYWORDS = (
    "clase",
    "reunión",
    "reunion",
    "personal",
    "cita",
    "recordatorio",
    "descanso",
    "comida",
    "cena",
    "gimnasio",
    "gym",
    "junta",
    "social",
    "fiesta",
    "cumpleaños",
    "cumpleanos",
    "viaje",
    "vacaciones",
)


def is_task_event(summary: str) -> bool:
    """Indica si el título de un evento representa una tarea académica."""
    text = (summary or "").strip().lower()
    if not text:
        return False
    if any(keyword in text for keyword in _NON_TASK_KEYWORDS):
        return False
    return any(keyword in text for keyword in _TASK_KEYWORDS)
