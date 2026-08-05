from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_local_frontend_preflight_allows_generic_write_methods_and_headers() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        response = client.options(
            "/api/settings/general",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type,x-actor-id,x-actor-role",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert "PUT" in response.headers["access-control-allow-methods"]
    assert "PATCH" in response.headers["access-control-allow-methods"]
    assert "x-actor-id" in response.headers["access-control-allow-headers"].lower()


def test_frontend_can_read_request_diagnostic_headers() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        response = client.get(
            "/api/health/live",
            headers={"Origin": "http://127.0.0.1:3000"},
        )

    exposed = response.headers["access-control-expose-headers"].lower()
    assert "server-timing" in exposed
    assert "x-support-copilot-timing" in exposed
    assert "x-correlation-id" in exposed
