"""Helpers para simular httpx en los tests de integraciones externas."""


class FakeResponse:
    def __init__(self, status_code: int, json_data=None, text: str = "", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json


class FakeAsyncClient:
    """Simula ``httpx.AsyncClient`` devolviendo respuestas en orden."""

    def __init__(self, responses):
        self._responses = list(responses) if isinstance(responses, list) else [responses]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, *args, **kwargs):
        if not self._responses:
            raise AssertionError("no quedan respuestas simuladas")
        return self._responses.pop(0)

    async def post(self, *args, **kwargs):
        return await self.request(*args, **kwargs)

    async def get(self, *args, **kwargs):
        return await self.request(*args, **kwargs)


def install_fake_httpx(monkeypatch, responses):
    """Parchea ``httpx.AsyncClient`` para devolver ``responses`` (en orden).

    Se reutiliza una única instancia, de modo que las respuestas se consumen
    secuencialmente incluso cuando el código crea varios clientes (paginación,
    reintentos).
    """
    client = FakeAsyncClient(responses)
    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: client)
