import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.identity import ActorContext
from app.main import create_app
from app.security.authentication import (
    AuthenticationRequest,
    WorkspaceAccessDenied,
    WorkspaceSelectionRequired,
)


class FailingAuthProvider:
    def __init__(self, exception: Exception) -> None:
        self._exception = exception

    def authenticate(
        self,
        actor_id: str | None,
        *,
        request: AuthenticationRequest | None = None,
    ) -> ActorContext:
        del actor_id, request
        raise self._exception


def test_session_requires_known_identity() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        missing = client.get("/api/session")
        unknown = client.get("/api/session", headers={"X-Actor-ID": "USR-9999"})

    assert missing.status_code == 401
    assert unknown.status_code == 401
    assert missing.json()["error"]["code"] == "authentication_required"


def test_session_ignores_client_supplied_role() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        response = client.get(
            "/api/session",
            headers={"X-Actor-ID": "USR-0001", "X-Actor-Role": "administrator"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["role"] == "specialist"
    assert "member:manage" not in payload["data"]["permissions"]
    assert payload["data"]["organization_id"] == "ORG-0001"
    assert payload["data"]["organization"] == {
        "id": "ORG-0001",
        "name": "Northstar Cloud",
        "slug": "northstar-cloud",
        "version": 1,
        "locale": "en-US",
        "time_zone": "Asia/Jakarta",
    }
    assert payload["meta"]["contract_version"] == "2026-07-22"


def test_provider_mode_fails_closed_until_adapter_is_configured() -> None:
    app = create_app(
        Settings(environment="test", auth_mode="provider", database_url=None, _env_file=None)
    )

    with TestClient(app) as client:
        response = client.get("/api/session", headers={"X-Actor-ID": "USR-0003"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "authentication_unavailable"


@pytest.mark.parametrize(
    ("exception", "status_code", "error_code"),
    [
        (
            WorkspaceAccessDenied("missing membership"),
            403,
            "workspace_access_denied",
        ),
        (
            WorkspaceSelectionRequired("multiple memberships"),
            409,
            "workspace_selection_required",
        ),
    ],
)
def test_provider_membership_failures_have_actionable_contracts(
    exception: Exception,
    status_code: int,
    error_code: str,
) -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))
    app.state.auth_provider = FailingAuthProvider(exception)

    with TestClient(app) as client:
        response = client.get("/api/session")

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code


def test_provider_cors_allows_bearer_auth_but_rejects_demo_identity_headers() -> None:
    app = create_app(
        Settings(
            environment="test",
            auth_mode="provider",
            database_url=None,
            _env_file=None,
        )
    )
    base_headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    }

    with TestClient(app) as client:
        bearer_preflight = client.options(
            "/api/session",
            headers={
                **base_headers,
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        demo_header_preflight = client.options(
            "/api/session",
            headers={
                **base_headers,
                "Access-Control-Request-Headers": "X-Actor-ID",
            },
        )

    assert bearer_preflight.status_code == 200
    assert demo_header_preflight.status_code == 400
