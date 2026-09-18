"""Tests de deduplicación de eventos."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.integrations.google.dedup import (
    are_high_confidence_duplicates,
    date_key,
    fingerprint,
    normalize_title,
)

TZ = "America/Tijuana"


def _dt(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 9, day, hour, 0, tzinfo=ZoneInfo(TZ))


def test_normalize_title() -> None:
    assert normalize_title("  Actividad   3 ") == "actividad 3"
    assert normalize_title("Actividad 3") == normalize_title("actividad 3")


def test_identical_events_are_duplicates() -> None:
    fp1 = fingerprint(title="Actividad 3", due_at=_dt(4), timezone=TZ, subject=None)
    fp2 = fingerprint(title="  Actividad   3 ", due_at=_dt(4), timezone=TZ, subject=None)
    assert are_high_confidence_duplicates(fp1, fp2) is True


def test_different_date_not_duplicate() -> None:
    fp1 = fingerprint(title="Actividad 3", due_at=_dt(4), timezone=TZ, subject=None)
    fp2 = fingerprint(title="Actividad 3", due_at=_dt(5), timezone=TZ, subject=None)
    assert are_high_confidence_duplicates(fp1, fp2) is False


def test_different_subject_not_duplicate() -> None:
    fp1 = fingerprint(title="Entrega 1", due_at=_dt(4), timezone=TZ, subject="Cálculo")
    fp2 = fingerprint(title="Entrega 1", due_at=_dt(4), timezone=TZ, subject="Física")
    assert are_high_confidence_duplicates(fp1, fp2) is False


def test_date_key_uses_event_timezone() -> None:
    # 2026-09-05 02:00 UTC == 2026-09-04 19:00 en Tijuana (UTC-7)
    dt = datetime(2026, 9, 5, 2, 0, tzinfo=ZoneInfo("UTC"))
    assert date_key(dt, TZ) == "2026-09-04"
    assert date_key(dt, None) == "2026-09-05"
