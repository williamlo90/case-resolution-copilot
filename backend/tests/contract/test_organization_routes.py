from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_organization_routes_authenticate_before_dependency_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        unauthenticated = client.get("/api/organizations/current")
        forbidden = client.get("/api/invitations", headers={"X-Actor-ID": "USR-0001"})
        unavailable = client.get("/api/organizations/current", headers={"X-Actor-ID": "USR-0003"})

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "organization_forbidden"
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "database_not_configured"
