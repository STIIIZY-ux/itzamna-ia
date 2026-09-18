"""Errores de dominio."""


class DomainError(Exception):
    """Error base del dominio de Itzamná IA."""


class NotFoundError(DomainError):
    """La entidad solicitada no existe o no pertenece al usuario."""


class InvalidStateTransitionError(DomainError):
    """Transición de estado no permitida."""

    def __init__(self, source: str, target: str) -> None:
        self.source = source
        self.target = target
        super().__init__(
            f"Transición no permitida: '{source}' -> '{target}'"
        )


class DuplicateError(DomainError):
    """Violación de unicidad (p. ej. materia o evento externo duplicado)."""
