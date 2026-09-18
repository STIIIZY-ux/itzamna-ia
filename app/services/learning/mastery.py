"""Actualización determinista de la métrica de dominio (0..1)."""

from __future__ import annotations

MAX_STEP = 0.2  # cambio máximo por una sola respuesta


def update_mastery(current: float, *, correct: bool, difficulty: int = 2) -> float:
    """Devuelve el nuevo dominio, con cambio acotado (<= 0.2 por respuesta).

    La dificultad (1..3) escala el paso. Una sola respuesta nunca produce un
    salto extremo; el dominio converge de forma gradual.
    """
    current = min(1.0, max(0.0, float(current)))
    weight = max(1, min(3, int(difficulty))) / 3.0  # 0.33..1.0
    delta = MAX_STEP * weight
    if correct:
        return round(min(1.0, current + delta), 4)
    return round(max(0.0, current - delta), 4)
