"""Tests de preferencias de notificación (pausa, modo)."""

from datetime import datetime, timedelta, timezone

from app.domain.enums import AccountabilityMode
from app.services.notification_preferences import NotificationPreferencesService


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=900)
    return user.id


async def test_pause_and_resume(session, session_factory, user_service) -> None:
    service = NotificationPreferencesService(session_factory)
    uid = await _make_user(user_service)

    await service.pause(uid, minutes=30)
    assert await service.is_paused(uid) is True

    await service.resume(uid)
    assert await service.is_paused(uid) is False


async def test_set_mode(session, session_factory, user_service) -> None:
    service = NotificationPreferencesService(session_factory)
    uid = await _make_user(user_service)

    prefs = await service.set_mode(uid, AccountabilityMode.GUERRA)
    assert prefs.mode is AccountabilityMode.GUERRA


async def test_is_paused_respects_expiry(session, session_factory, user_service) -> None:
    service = NotificationPreferencesService(session_factory)
    uid = await _make_user(user_service)

    await service.pause(uid, minutes=30)
    now = datetime.now(timezone.utc)
    assert await service.is_paused(uid, now=now) is True
    assert await service.is_paused(uid, now=now + timedelta(hours=1)) is False
