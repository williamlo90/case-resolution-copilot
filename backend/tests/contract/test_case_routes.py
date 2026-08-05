from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_case_routes_authorize_before_database_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        unauthenticated = client.get("/api/cases")
        read_unavailable = client.get("/api/cases", headers={"X-Actor-ID": "USR-0001"})
        history_unauthenticated = client.get(
            "/api/cases/CS-2048/conversation/history"
        )
        history_unavailable = client.get(
            "/api/cases/CS-2048/activity/history",
            headers={"X-Actor-ID": "USR-0004"},
        )
        write_forbidden = client.post(
            "/api/cases/CS-2048/assign",
            headers={"X-Actor-ID": "USR-0004", "X-Actor-Role": "administrator"},
            json={"expected_version": 1},
        )
        write_unavailable = client.post(
            "/api/cases/CS-2048/assign",
            headers={"X-Actor-ID": "USR-0001"},
            json={"expected_version": 1},
        )

    assert unauthenticated.status_code == 401
    assert read_unavailable.status_code == 503
    assert read_unavailable.json()["error"]["code"] == "database_not_configured"
    assert history_unauthenticated.status_code == 401
    assert history_unavailable.status_code == 503
    assert write_forbidden.status_code == 403
    assert write_forbidden.json()["error"]["code"] == "case_manage_forbidden"
    assert write_unavailable.status_code == 503
