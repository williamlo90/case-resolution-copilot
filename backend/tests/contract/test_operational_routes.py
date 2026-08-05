from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_operational_routes_authorize_before_database_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        unauthenticated = client.get("/api/notifications")
        notification_unavailable = client.get(
            "/api/notifications",
            headers={"X-Actor-ID": "USR-0001"},
        )
        quality_forbidden = client.get(
            "/api/quality",
            headers={"X-Actor-ID": "USR-0001"},
        )
        quality_unavailable = client.get(
            "/api/quality",
            headers={"X-Actor-ID": "USR-0002"},
        )
        settings_forbidden = client.get(
            "/api/settings/general",
            headers={"X-Actor-ID": "USR-0002"},
        )
        settings_unavailable = client.get(
            "/api/settings/general",
            headers={"X-Actor-ID": "USR-0003"},
        )
        audit_forbidden = client.post(
            "/api/cases/CS-2048/audit-export",
            headers={"X-Actor-ID": "USR-0002"},
        )
        audit_unavailable = client.post(
            "/api/cases/CS-2048/audit-export",
            headers={"X-Actor-ID": "USR-0004"},
        )

    assert unauthenticated.status_code == 401
    assert notification_unavailable.status_code == 503
    assert quality_forbidden.status_code == 403
    assert quality_forbidden.json()["error"]["code"] == "quality_read_forbidden"
    assert quality_unavailable.status_code == 503
    assert settings_forbidden.status_code == 403
    assert settings_forbidden.json()["error"]["code"] == "settings_manage_forbidden"
    assert settings_unavailable.status_code == 503
    assert audit_forbidden.status_code == 403
    assert audit_forbidden.json()["error"]["code"] == "audit_read_forbidden"
    assert audit_unavailable.status_code == 503


def test_member_commands_require_administrator_authority_before_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))
    command = {
        "expected_version": 1,
        "role": "supervisor",
    }

    with TestClient(app) as client:
        forbidden = client.patch(
            "/api/members/USR-0001",
            headers={"X-Actor-ID": "USR-0002"},
            json=command,
        )
        unavailable = client.patch(
            "/api/members/USR-0001",
            headers={"X-Actor-ID": "USR-0003"},
            json=command,
        )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "organization_forbidden"
    assert unavailable.status_code == 503


def test_openapi_exposes_the_b7_surface_without_legacy_travel_fields() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))
    schema = app.openapi()
    expected_paths = {
        "/api/quality",
        "/api/quality/cases/{case_id}",
        "/api/cases/{case_id}/audit-export",
        "/api/notifications",
        "/api/notifications/read-all",
        "/api/notifications/{notification_id}/read",
        "/api/members/{member_id}",
        "/api/invitations/{invitation_id}/revoke",
        "/api/settings/{section}",
    }

    assert expected_paths <= set(schema["paths"])
    b7_schema = str(
        {
            path: schema["paths"][path]
            for path in expected_paths
        }
    ).lower()
    assert all(
        travel_word not in b7_schema
        for travel_word in ("passenger", "airline", "itinerary", "booking_id")
    )


def test_invalid_governance_settings_fail_before_database_access() -> None:
    app = create_app(Settings(environment="test", database_url=None, _env_file=None))

    with TestClient(app) as client:
        invalid_retention = client.put(
            "/api/settings/retention",
            headers={"X-Actor-ID": "USR-0003"},
            json={
                "section": "retention",
                "expected_version": 1,
                "configuration": {
                    "audit_retention_days": 365,
                    "conversation_retention_days": 730,
                    "legal_hold_enabled": True,
                },
            },
        )
        invalid_currency = client.put(
            "/api/settings/approvals",
            headers={"X-Actor-ID": "USR-0003"},
            json={
                "section": "approvals",
                "expected_version": 1,
                "configuration": {
                    "administrator_financial_limits": {"DOLLARS": "100.00"},
                    "require_decision_reason": True,
                },
            },
        )

    assert invalid_retention.status_code == 422
    assert invalid_currency.status_code == 422
