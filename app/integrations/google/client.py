"""Cliente async de la API de Google Calendar (solo lectura)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from .errors import (
    GoogleApiError,
    GoogleRateLimitError,
    GoogleServiceUnavailableError,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com"
_ACCESS_TOKEN_BUFFER_SECONDS = 300  # refresca el token si expira en < 5 min


class GoogleCalendarClient:
    """Cliente de lectura de eventos de Google Calendar."""

    def __init__(
        self,
        get_access_token: Callable[[int], Awaitable[str]],
        *,
        timeout: float = 20.0,
        max_retries: int = 3,
    ) -> None:
        self._get_access_token = get_access_token
        self._timeout = timeout
        self._max_retries = max_retries

    async def list_events(
        self,
        *,
        user_id: int,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[dict]:
        """Lista todos los eventos en el rango dado (con paginación)."""
        events: list[dict] = []
        page_token: str | None = None
        params: dict = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": _rfc3339(time_min),
            "timeMax": _rfc3339(time_max),
            "maxResults": "2500",
        }
        while True:
            if page_token:
                params["pageToken"] = page_token
            data = await self._request(
                user_id=user_id,
                method="GET",
                path=f"/calendar/v3/calendars/{quote(calendar_id, safe='')}/events",
                params=dict(params),
            )
            events.extend(data.get("items") or [])
            page_token = data.get("nextPageToken")
            if not page_token:
                return events

    async def _request(
        self, *, user_id: int, method: str, path: str, params: dict
    ) -> dict:
        token = await self._get_access_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{_BASE_URL}{path}"

        for attempt in range(self._max_retries + 1):
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as client:
                response = await client.request(method, url, params=params, headers=headers)

            if response.status_code == 401 and attempt == 0:
                # El token pudo expirar entre el refresh y la llamada.
                token = await self._get_access_token(user_id)
                headers = {"Authorization": f"Bearer {token}"}
                continue

            if response.status_code == 429:
                retry_after = _retry_after_seconds(response)
                if attempt < self._max_retries:
                    await asyncio.sleep(retry_after)
                    continue
                raise GoogleRateLimitError()

            if response.status_code >= 500:
                if attempt < self._max_retries:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise GoogleServiceUnavailableError()

            if response.status_code >= 400:
                raise GoogleApiError(response.status_code, response.text[:200])

            try:
                return response.json()
            except ValueError as exc:
                raise GoogleApiError(response.status_code, "respuesta no-JSON") from exc

        raise GoogleServiceUnavailableError()


def _rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _retry_after_seconds(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After")
    if value:
        try:
            return float(value)
        except ValueError:
            return 2.0
    return 2.0


def _backoff(attempt: int) -> float:
    return 2.0 * (2**attempt)
