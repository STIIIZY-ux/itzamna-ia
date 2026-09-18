"""Repetición espaciada determinista (simple, persistente, sin RAM)."""

from __future__ import annotations

from datetime import datetime, timedelta

#: Intervalos base (horas) según dificultad cuando la respuesta es correcta.
_BASE_HOURS = {1: 4.0, 2: 24.0, 3: 72.0}
_INCORRECT_MINUTES = 30


def next_review_at(
    now: datetime,
    *,
    correct: bool,
    difficulty: int = 2,
    mastery: float = 0.5,
) -> datetime:
    """Calcula el próximo repaso a partir de respuesta, dificultad y dominio.

    - Incorrecta -> repasar en 30 minutos.
    - Correcta -> intervalo base por dificultad, escalado por el dominio.
    """
    if not correct:
        return now + timedelta(minutes=_INCORRECT_MINUTES)

    base = _BASE_HOURS.get(int(difficulty), 24.0)
    factor = 0.5 + min(1.0, max(0.0, mastery))  # 0.5..1.5
    return now + timedelta(hours=base * factor)
