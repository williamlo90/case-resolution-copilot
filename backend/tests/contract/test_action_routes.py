from fastapi.testclient import TestClient

from app.api.routes.actions import _translate as translate_action
from app.api.routes.connections import _translate as translate_connection
from app.config import Settings
from app.domain.actions import (
    ActionExecutionBlocked,
    ActionExecutionBlocker,
    ActionVersionConflict,
    InvalidActionCursor,
)
from app.domain.connections import (
    ConnectionVersionConflict,
    InvalidConnectionCursor,
)
from app.main import create_app


def test_action_routes_authorize_before_database_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        unauthenticated = client.get("/api/actions")
        read_unavailable = client.get(
            "/api/actions",
            headers={"X-Actor-ID": "USR-0001"},
        )
        forbidden_execute = client.post(
            "/api/actions/AC-TEST/execute",
            headers={
                "X-Actor-ID": "USR-0001",
                "X-Actor-Role": "administrator",
            },
            json={"expected_version": 1},
        )
        execute_unavailable = client.post(
            "/api/actions/AC-TEST/execute",
            headers={"X-Actor-ID": "USR-0002"},
            json={"expected_version": 1},
        )
        reconcile_forbidden = client.post(
            "/api/actions/AC-TEST/reconcile",
            headers={"X-Actor-ID": "USR-0004"},
            json={"expected_version": 1},
        )

    assert unauthenticated.status_code == 401
    assert read_unavailable.status_code == 503
    assert forbidden_execute.status_code == 403
    assert forbidden_execute.json()["error"]["code"] == "action_execute_forbidden"
    assert execute_unavailable.status_code == 503
    assert reconcile_forbidden.status_code == 403


def test_connection_routes_authorize_before_database_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        read_unavailable = client.get(
            "/api/connections",
            headers={"X-Actor-ID": "USR-0002"},
        )
        forbidden_test = client.post(
            "/api/connections/CN-TEST/test",
            headers={
                "X-Actor-ID": "USR-0002",
                "X-Actor-Role": "administrator",
            },
            json={"expected_version": 1},
        )
        test_unavailable = client.post(
            "/api/connections/CN-TEST/test",
            headers={"X-Actor-ID": "USR-0003"},
            json={"expected_version": 1},
        )

    assert read_unavailable.status_code == 503
    assert forbidden_test.status_code == 403
    assert forbidden_test.json()["error"]["code"] == "connection_manage_forbidden"
    assert test_unavailable.status_code == 503


def test_action_and_connection_errors_are_distinct_and_actionable() -> None:
    action_cursor = translate_action(InvalidActionCursor("The action cursor is invalid."))
    action_version = translate_action(ActionVersionConflict(expected_version=2, current_version=3))
    blocked = translate_action(
        ActionExecutionBlocked(
            ActionExecutionBlocker.CONNECTION_UNAVAILABLE,
            "The target connection is unavailable.",
        )
    )
    connection_cursor = translate_connection(
        InvalidConnectionCursor("The connection cursor is invalid.")
    )
    connection_version = translate_connection(
        ConnectionVersionConflict(expected_version=1, current_version=2)
    )

    assert (action_cursor.status_code, action_cursor.code) == (
        400,
        "invalid_action_cursor",
    )
    assert (action_version.status_code, action_version.code) == (
        409,
        "version_conflict",
    )
    assert (blocked.status_code, blocked.code) == (
        424,
        "action_execution_blocked",
    )
    assert blocked.details == {"blocker": "connection_unavailable"}
    assert (connection_cursor.status_code, connection_cursor.code) == (
        400,
        "invalid_connection_cursor",
    )
    assert (connection_version.status_code, connection_version.code) == (
        409,
        "version_conflict",
    )


def test_openapi_exposes_the_complete_b6_surface() -> None:
    schema = create_app(Settings(environment="test", database_url=None, _env_file=None)).openapi()
    paths = set(schema["paths"])

    assert {
        "/api/actions",
        "/api/actions/{action_id}",
        "/api/actions/{action_id}/execute",
        "/api/actions/{action_id}/retry",
        "/api/actions/{action_id}/reconcile",
        "/api/actions/{action_id}/manual-outcome",
        "/api/actions/{action_id}/escalate",
        "/api/connections",
        "/api/connections/{connection_id}",
        "/api/connections/{connection_id}/test",
    } <= paths
    assert "legacy_import" not in schema["components"]["schemas"]["ActionCommand"]["enum"]
