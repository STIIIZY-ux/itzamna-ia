"""Errores de la integración con Google."""


class GoogleIntegrationError(Exception):
    """Error base de la integración con Google."""


class GoogleAuthError(GoogleIntegrationError):
    """Error de autenticación OAuth (credenciales, refresh, revocación)."""


class GoogleAccessRevokedError(GoogleAuthError):
    """El acceso fue revocado o el refresh token dejó de ser válido."""


class GoogleRateLimitError(GoogleIntegrationError):
    """Se alcanzó el límite de cuota (HTTP 429)."""


class GoogleServiceUnavailableError(GoogleIntegrationError):
    """Google devolvió un error temporal (5xx)."""


class GoogleApiError(GoogleIntegrationError):
    """Error de la API con un código de estado HTTP conocido."""

    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        super().__init__(f"Google API error {status_code}: {message}")
