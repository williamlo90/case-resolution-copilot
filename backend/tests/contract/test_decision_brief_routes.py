from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_decision_brief_routes_authorize_before_database_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        unauthenticated = client.post(
            "/api/cases/CS-2047/proposals",
            json={"expected_case_version": 1},
        )
        spoofed = client.post(
            "/api/cases/CS-2047/proposals",
            headers={"X-Actor-ID": "USR-0004", "X-Actor-Role": "specialist"},
            json={"expected_case_version": 1},
        )
        generate_unavailable = client.post(
            "/api/cases/CS-2047/proposals",
            headers={"X-Actor-ID": "USR-0001"},
            json={"expected_case_version": 1},
        )
        read_unavailable = client.get(
            "/api/cases/CS-2047/proposals/current",
            headers={"X-Actor-ID": "USR-0004"},
        )

    assert unauthenticated.status_code == 401
    assert spoofed.status_code == 403
    assert spoofed.json()["error"]["code"] == "case_manage_forbidden"
    assert generate_unavailable.status_code == 503
    assert read_unavailable.status_code == 503
