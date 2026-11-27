from fastapi.testclient import TestClient

from emporio import __version__
from emporio.api.app import app


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
