from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_policy_routes_authorize_before_database_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        unauthenticated = client.get("/api/policies")
        read_unavailable = client.get("/api/policies", headers={"X-Actor-ID": "USR-0004"})
        spoofed_write = client.post(
            "/api/policies",
            headers={"X-Actor-ID": "USR-0001", "X-Actor-Role": "administrator"},
            json={
                "title": "Test policy",
                "description": "Test policy description",
                "source": {"kind": "manual", "name": "Test source"},
            },
        )
        write_unavailable = client.post(
            "/api/policies",
            headers={"X-Actor-ID": "USR-0003"},
            json={
                "title": "Test policy",
                "description": "Test policy description",
                "source": {"kind": "manual", "name": "Test source"},
            },
        )

    assert unauthenticated.status_code == 401
    assert read_unavailable.status_code == 503
    assert spoofed_write.status_code == 403
    assert spoofed_write.json()["error"]["code"] == "policy_manage_forbidden"
    assert write_unavailable.status_code == 503
