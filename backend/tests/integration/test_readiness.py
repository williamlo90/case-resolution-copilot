from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_readiness_reports_real_postgresql_health(
    test_database_url: str, migrated_database: None
) -> None:
    app = create_app(
        Settings(
            environment="test",
            database_url=test_database_url,
            _env_file=None,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "support-copilot-api",
        "dependencies": {"database": {"status": "healthy"}},
    }


def test_readiness_rejects_unavailable_postgresql() -> None:
    app = create_app(
        Settings(
            environment="test",
            database_url="postgresql+psycopg://travelops:travelops@127.0.0.1:1/unavailable",
            _env_file=None,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"]["database"]["status"] == "unavailable"
