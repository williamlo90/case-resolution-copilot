from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_liveness_reports_the_service_identity() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "support-copilot-api",
    }
