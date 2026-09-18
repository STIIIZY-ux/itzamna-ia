"""Máquina de estados de :class:`TaskStatus`.

Define las transiciones válidas entre estados. Mantener el control aquí
(única fuente de verdad) evita transiciones imposibles en cualquier parte
del sistema.
"""

from .enums import TaskStatus

#: Transiciones válidas desde cada estado. La clave es el estado origen.
ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDIENTE: frozenset(
        {
            TaskStatus.NOTIFICADA,
            TaskStatus.COMPROMISO,
            TaskStatus.INICIADA,
            TaskStatus.BLOQUEADA,
        }
    ),
    TaskStatus.NOTIFICADA: frozenset(
        {
            TaskStatus.COMPROMISO,
            TaskStatus.INICIADA,
            TaskStatus.PENDIENTE,
        }
    ),
    TaskStatus.COMPROMISO: frozenset(
        {
            TaskStatus.INICIADA,
            TaskStatus.BLOQUEADA,
            TaskStatus.PENDIENTE,
        }
    ),
    TaskStatus.INICIADA: frozenset(
        {
            TaskStatus.EN_PROGRESO,
            TaskStatus.BLOQUEADA,
            TaskStatus.TERMINADA,
        }
    ),
    TaskStatus.EN_PROGRESO: frozenset(
        {
            TaskStatus.TERMINADA,
            TaskStatus.ENTREGADA,
            TaskStatus.BLOQUEADA,
        }
    ),
    TaskStatus.TERMINADA: frozenset({TaskStatus.ENTREGADA}),
    TaskStatus.ENTREGADA: frozenset(),
    TaskStatus.BLOQUEADA: frozenset(
        {
            TaskStatus.PENDIENTE,
            TaskStatus.INICIADA,
            TaskStatus.EN_PROGRESO,
        }
    ),
}


def can_transition(source: TaskStatus, target: TaskStatus) -> bool:
    """Indica si la transición ``source -> target`` está permitida."""
    return target in ALLOWED_TRANSITIONS.get(source, frozenset())
