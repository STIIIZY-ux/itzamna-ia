"""Tests del cliente de Google Calendar (client.py) con httpx simulado."""

from datetime import datetime, timezone

import pytest

from app.integrations.google.client import GoogleCalendarClient
from app.integrations.google.errors import GoogleApiError, GoogleRateLimitError
from tests.fake_http import FakeResponse, install_fake_httpx


def _client(get_access_token):
    return GoogleCalendarClient(get_access_token)


async def _fake_token(user_id: int) -> str:
    return "tok"


def _range():
    return datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 10, 1, tzinfo=timezone.utc)


async def test_list_events_single_page(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(200, {"items": [{"id": "e1"}, {"id": "e2"}]}))
    client = _client(_fake_token)
    events = await client.list_events(
        user_id=1, calendar_id="primary", time_min=_range()[0], time_max=_range()[1]
    )
    assert [e["id"] for e in events] == ["e1", "e2"]


async def test_list_events_pagination(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        [
            FakeResponse(200, {"items": [{"id": "e1"}], "nextPageToken": "tok2"}),
            FakeResponse(200, {"items": [{"id": "e2"}]}),
        ],
    )
    client = _client(_fake_token)
    events = await client.list_events(
        user_id=1, calendar_id="primary", time_min=_range()[0], time_max=_range()[1]
    )
    assert [e["id"] for e in events] == ["e1", "e2"]


async def test_list_events_retries_429(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        [
            FakeResponse(429, {}, headers={"Retry-After": "0"}),
            FakeResponse(200, {"items": [{"id": "e1"}]}),
        ],
    )
    client = _client(_fake_token)
    events = await client.list_events(
        user_id=1, calendar_id="primary", time_min=_range()[0], time_max=_range()[1]
    )
    assert [e["id"] for e in events] == ["e1"]


async def test_list_events_429_exhausted(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch, [FakeResponse(429, {}, headers={"Retry-After": "0"}) for _ in range(4)]
    )
    client = _client(_fake_token)
    with pytest.raises(GoogleRateLimitError):
        await client.list_events(
            user_id=1, calendar_id="primary", time_min=_range()[0], time_max=_range()[1]
        )


async def test_list_events_403_raises(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(403, text="forbidden"))
    client = _client(_fake_token)
    with pytest.raises(GoogleApiError):
        await client.list_events(
            user_id=1, calendar_id="primary", time_min=_range()[0], time_max=_range()[1]
        )
