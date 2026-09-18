"""Errores de la capa de IA."""


class AIServiceError(Exception):
    """Error base de la capa de IA."""


class AIConfigError(AIServiceError):
    """Configuración de IA inválida o ausente."""


class AIProviderError(AIServiceError):
    """El proveedor devolvió un error."""


class AIRateLimitError(AIServiceError):
    """Se alcanzó el límite de cuota del proveedor (429)."""


class AITimeoutError(AIServiceError):
    """La llamada al proveedor superó el timeout."""


class AIInvalidResponseError(AIServiceError):
    """La respuesta del proveedor no es válida/no parseable."""
