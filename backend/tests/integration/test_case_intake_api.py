import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.integrations.webhook_security import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    sign_webhook,
)
from app.main import create_app
from app.persistence.database import Database
from app.persistence.models import AuditEventModel, ConnectionModel, OrganizationModel

SECRET = "case-signing-secret-with-at-least-32-characters"


def _payload(*, issue: str = "Customer reports a duplicate invoice charge") -> dict[str, object]:
    return {
        "event_id": "helpdesk:case-1001",
        "external_reference": "INV-1001",
        "category": "billing_dispute",
        "issue": issue,
        "urgency": "high",
        "risk": "medium",
        "due_at": "2026-07-29T12:00:00Z",
        "impact_amount": "125.00",
        "impact_currency": "USD",
        "source_freshness": "current",
        "source_checked_at": "2026-07-28T12:00:00Z",
        "request": {
            "channel": "webhook",
            "customer_message": "I was charged twice.",
            "summary": "Possible duplicate charge.",
            "received_at": "2026-07-28T11:55:00Z",
        },
        "customer": {
            "customer_id": "CUS-1001",
            "name": "Taylor Morgan",
            "tier": "standard",
            "locale": "en-US",
            "contact": "taylor@example.com",
        },
        "business_contexts": [
            {
                "type": "invoice",
                "label": "Invoice INV-1001",
                "source": "billing",
                "source_reference": "INV-1001",
                "status": "paid",
                "fields": {"amount": "125.00", "currency": "USD"},
                "captured_at": "2026-07-28T12:00:00Z",
                "freshness": "current",
                "checked_at": "2026-07-28T12:00:00Z",
            }
        ],
    }


def _signed(body: bytes) -> dict[str, str]:
    timestamp = int(datetime.now(UTC).timestamp())
    return {
        TIMESTAMP_HEADER: str(timestamp),
        SIGNATURE_HEADER: sign_webhook(
            secret=SECRET,
            timestamp=timestamp,
            body=body,
        ),
        "Content-Type": "application/json",
    }


def test_signed_case_intake_is_tenant_bound_idempotent_and_conflict_safe(
    database: Database,
    test_database_url: str,
) -> None:
    with database.session() as session:
        session.add(
            OrganizationModel(
                public_id="ORG-0001",
                name="Northstar Cloud",
                slug="northstar-cloud",
            )
        )
    app = create_app(
        Settings(
            environment="test",
            database_url=test_database_url,
            case_source_provider="signed_webhook",
            integration_organization_id="ORG-0001",
            case_webhook_secret=SECRET,
            _env_file=None,
        )
    )
    body = json.dumps(_payload(), separators=(",", ":")).encode()
    changed = json.dumps(
        _payload(issue="Changed payload for the same source event"),
        separators=(",", ":"),
    ).encode()
    repeated_correlation_headers = {
        **_signed(body),
        "X-Correlation-ID": "corr_repeated_by_source",
    }

    with TestClient(app) as client:
        first = client.post(
            "/api/intake/cases",
            content=body,
            headers=repeated_correlation_headers,
        )
        duplicate = client.post(
            "/api/intake/cases",
            content=body,
            headers=repeated_correlation_headers,
        )
        conflict = client.post("/api/intake/cases", content=changed, headers=_signed(changed))

    assert first.status_code == 202
    assert first.json()["data"]["duplicate"] is False
    assert duplicate.status_code == 202
    assert duplicate.json()["data"]["id"] == first.json()["data"]["id"]
    assert duplicate.json()["data"]["duplicate"] is True
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "case_source_conflict"

    rollback_app = create_app(
        Settings(
            environment="test",
            database_url=test_database_url,
            integration_organization_id="ORG-0001",
            _env_file=None,
        )
    )
    with TestClient(rollback_app):
        pass

    with database.session() as session:
        intake_connection = session.scalar(
            select(ConnectionModel).where(ConnectionModel.public_id == "CN-WEBHOOK-INTAKE")
        )
        imported = list(
            session.scalars(
                select(AuditEventModel).where(AuditEventModel.event_type == "case.imported")
            )
        )
        assert intake_connection is not None
        assert intake_connection.health == "not_configured"
        assert intake_connection.credential_status == "missing"
        assert len(imported) == 1
        assert "customer_message" not in imported[0].data
