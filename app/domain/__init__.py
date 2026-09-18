"""Dominio de Itzamná IA: enums, máquina de estados y errores de dominio."""

from .enums import (
    AccountabilityMode,
    AccountabilityState,
    CommitmentStatus,
    HistoryEventType,
    JobKind,
    JobStatus,
    ResourceStatus,
    ResourceType,
    RiskLevel,
    TaskPriority,
    TaskSource,
    TaskStatus,
)
from .errors import (
    DomainError,
    DuplicateError,
    InvalidStateTransitionError,
    NotFoundError,
)
from .state_machine import ALLOWED_TRANSITIONS, can_transition

__all__ = [
    "ALLOWED_TRANSITIONS",
    "AccountabilityMode",
    "AccountabilityState",
    "CommitmentStatus",
    "DomainError",
    "DuplicateError",
    "HistoryEventType",
    "InvalidStateTransitionError",
    "JobKind",
    "JobStatus",
    "NotFoundError",
    "ResourceStatus",
    "ResourceType",
    "RiskLevel",
    "TaskPriority",
    "TaskSource",
    "TaskStatus",
    "can_transition",
]
