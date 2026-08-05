import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/tasks", None),
        ("GET", "/api/tasks/RF-1042", None),
        ("POST", "/api/tasks/RF-1042/agent-runs", {}),
        ("GET", "/api/agent-runs/AR-8821", None),
        ("POST", "/api/tasks/RF-1042/proposals/1/reserve", {"ttl_minutes": 15}),
        (
            "POST",
            "/api/tasks/RF-1042/proposals/1/decisions",
            {
                "reservation_id": "00000000-0000-0000-0000-000000000001",
                "expected_evidence_fingerprint": "a" * 64,
                "outcome": "approved",
                "reason": "Verified compatibility request.",
            },
        ),
    ],
)
def test_legacy_workflow_routes_are_not_mounted(
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            json=payload,
            headers={"X-Actor-ID": "USR-0003"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"
