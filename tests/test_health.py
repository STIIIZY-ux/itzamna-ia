"""Tests del endpoint /health."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_unhealthy_by_default() -> None:
    app.state.bot_ready = False
    app.state.db_ready = False
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy"}


def test_health_ok_when_ready() -> None:
    app.state.bot_ready = True
    app.state.db_ready = True
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_unhealthy_when_db_down() -> None:
    app.state.bot_ready = True
    app.state.db_ready = False
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
