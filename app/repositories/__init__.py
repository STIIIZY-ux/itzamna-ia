"""Repositorios de acceso a datos de Itzamná IA."""

from .accountability import AccountabilityRepository
from .commitments import CommitmentRepository
from .google_credentials import GoogleCredentialRepository
from .learning import (
    BookRepository,
    ChapterRepository,
    ConceptRepository,
    FlashcardRepository,
    QuestionRepository,
    QuizAnswerRepository,
    QuizRepository,
)
from .notification_preferences import NotificationPreferencesRepository
from .resources import ResourceRepository
from .scheduled_jobs import ScheduledJobRepository
from .subjects import SubjectRepository
from .task_sources import TaskSourceRepository
from .tasks import TaskRepository
from .users import UserRepository

__all__ = [
    "AccountabilityRepository",
    "BookRepository",
    "ChapterRepository",
    "CommitmentRepository",
    "ConceptRepository",
    "FlashcardRepository",
    "GoogleCredentialRepository",
    "NotificationPreferencesRepository",
    "QuestionRepository",
    "QuizAnswerRepository",
    "QuizRepository",
    "ResourceRepository",
    "ScheduledJobRepository",
    "SubjectRepository",
    "TaskRepository",
    "TaskSourceRepository",
    "UserRepository",
]
