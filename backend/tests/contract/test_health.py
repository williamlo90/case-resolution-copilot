import re

import pytest
from fastapi import HTTPException, Query
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.errors import AppError
from app.config import Settings
from app.main import create_app


def make_client() -> TestClient:
    return TestClient(create_app(Settings(environment="test", _env_file=None)))


def test_liveness_contract_and_generated_correlation_id() -> None:
    with make_client() as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "service": "support-copilot-api"}
    assert response.headers["X-Correlation-ID"].startswith("corr_")
    assert re.fullmatch(
        r"app;dur=\d+(?:\.\d{1,2})?",
        response.headers["Server-Timing"],
    )
    assert (
        response.headers["X-Support-Copilot-Timing"]
        == response.headers["Server-Timing"]
    )
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow, noarchive"
    assert "Content-Security-Policy" not in response.headers


def test_health_exposes_the_deployed_source_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = "a" * 40
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", revision)

    with make_client() as client:
        response = client.get("/api/health/live")

    assert response.headers["X-Source-Revision"] == revision


def test_production_disables_api_docs_and_adds_json_csp() -> None:
    app = create_app(
        Settings(
            environment="production",
            auth_mode="provider",
            database_url="postgresql+psycopg://user@example.invalid/support",
            clerk_secret_key=SecretStr("sk_contract_placeholder"),
            clerk_jwt_key=SecretStr(
                "-----BEGIN PUBLIC KEY-----\ncontract\n-----END PUBLIC KEY-----"
            ),
            clerk_authorized_parties="https://support.example.com",
            cors_origins="https://support.example.com",
            _env_file=None,
        )
    )

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None

    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )


def test_readiness_is_honest_about_unconfigured_database() -> None:
    with make_client() as client:
        response = client.get("/api/health/ready", headers={"X-Correlation-ID": "corr_contract"})

    assert response.status_code == 503
    assert response.headers["X-Correlation-ID"] == "corr_contract"
    assert response.json() == {
        "status": "not_ready",
        "service": "support-copilot-api",
        "dependencies": {"database": {"status": "not_configured"}},
    }


def test_openapi_exposes_generic_contracts_without_legacy_workflows() -> None:
    with make_client() as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/health/live" in paths
    assert "/api/health/ready" in paths
    assert "/api/cases" in paths
    assert "/api/reviews" in paths
    assert "/api/actions" in paths
    assert all("/api/tasks" not in path for path in paths)
    assert all("/api/agent-runs" not in path for path in paths)


def test_invalid_correlation_id_is_replaced() -> None:
    with make_client() as client:
        response = client.get("/api/health/live", headers={"X-Correlation-ID": "invalid value"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"].startswith("corr_")


def test_not_found_uses_standard_error_envelope() -> None:
    with make_client() as client:
        response = client.get("/api/does-not-exist", headers={"X-Correlation-ID": "corr_not_found"})

    assert response.status_code == 404
    assert response.headers["X-Correlation-ID"] == "corr_not_found"
    assert response.json() == {
        "error": {
            "code": "resource_not_found",
            "message": "Not Found",
            "correlation_id": "corr_not_found",
            "details": {},
        }
    }


def test_unexpected_error_is_redacted_and_correlated() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    @app.get("/api/test-only/failure")
    async def fail() -> None:
        raise RuntimeError("sensitive internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/test-only/failure", headers={"X-Correlation-ID": "corr_failure"}
        )

    assert response.status_code == 500
    assert response.headers["X-Correlation-ID"] == "corr_failure"
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "The request could not be completed.",
            "correlation_id": "corr_failure",
            "details": {},
        }
    }
    assert "sensitive internal detail" not in response.text


def test_server_http_exception_detail_is_redacted() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    @app.get("/api/test-only/http-failure")
    async def fail() -> None:
        raise HTTPException(status_code=503, detail="private upstream detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/test-only/http-failure",
            headers={"X-Correlation-ID": "corr_http_failure"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "The request could not be completed."
    assert "private upstream detail" not in response.text


def test_application_error_uses_standard_envelope() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    @app.get("/api/test-only/conflict")
    async def conflict() -> None:
        raise AppError(
            code="version_conflict",
            message="The record changed.",
            status_code=409,
            details={"expected_version": 1},
        )

    with TestClient(app) as client:
        response = client.get(
            "/api/test-only/conflict", headers={"X-Correlation-ID": "corr_conflict"}
        )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "version_conflict",
        "message": "The record changed.",
        "correlation_id": "corr_conflict",
        "details": {"expected_version": 1},
    }


def test_request_validation_uses_standard_envelope() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    @app.get("/api/test-only/validated")
    async def validated(limit: int = Query(ge=1, le=10)) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get(
            "/api/test-only/validated?limit=0",
            headers={"X-Correlation-ID": "corr_validation"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert response.json()["error"]["correlation_id"] == "corr_validation"
    assert response.json()["error"]["details"][0]["location"] == ["query", "limit"]
