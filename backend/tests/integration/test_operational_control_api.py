from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.notifications import (
    NotificationKind,
    NotificationResourceType,
    NotificationSeed,
)
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator
from app.integrations.quality_seed import deterministic_quality_projections
from app.main import create_app
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.models import MembershipModel, OrganizationModel
from app.persistence.notification_repository import NotificationRepository
from app.persistence.quality_repository import QualityRepository
from app.persistence.settings_repository import OrganizationSettingsRepository

ADMIN = {"X-Actor-ID": "USR-0003"}
AUDITOR = {"X-Actor-ID": "USR-0004"}
SPECIALIST = {"X-Actor-ID": "USR-0001"}
SUPERVISOR = {"X-Actor-ID": "USR-0002"}


def _seed(database: Database) -> None:
    with database.session() as session:
        organization = OrganizationModel(
            public_id="ORG-0001",
            name="Northstar Cloud",
            slug="northstar-cloud",
        )
        session.add(organization)
        session.flush()
        session.add_all(
            [
                MembershipModel(
                    public_id="USR-0001",
                    organization_id=organization.id,
                    subject_id="USR-0001",
                    name="Maya Specialist",
                    email="maya.specialist@example.com",
                    role="specialist",
                    status="active",
                ),
                MembershipModel(
                    public_id="USR-0002",
                    organization_id=organization.id,
                    subject_id="USR-0002",
                    name="Rina Supervisor",
                    email="rina.supervisor@example.com",
                    role="supervisor",
                    status="active",
                ),
                MembershipModel(
                    public_id="USR-0003",
                    organization_id=organization.id,
                    subject_id="USR-0003",
                    name="Ari Administrator",
                    email="ari.administrator@example.com",
                    role="administrator",
                    status="active",
                ),
                MembershipModel(
                    public_id="USR-0004",
                    organization_id=organization.id,
                    subject_id="USR-0004",
                    name="Nadia Auditor",
                    email="nadia.auditor@example.com",
                    role="auditor",
                    status="active",
                ),
            ]
        )
        session.flush()
        OrganizationSettingsRepository(session).ensure_defaults(
            organization_public_id="ORG-0001"
        )
        cases = DeterministicCaseSourceSimulator().fetch_cases()
        case_repository = CaseRepository(session)
        for command in cases:
            case_repository.seed_case(
                organization_public_id="ORG-0001",
                command=command,
                correlation_id=f"seed:{command.public_id}",
            )
        quality_repository = QualityRepository(session)
        for projection in deterministic_quality_projections():
            quality_repository.upsert_projection(
                organization_public_id="ORG-0001",
                seed=projection,
                correlation_id=f"quality:{projection.case_public_id}",
            )
        NotificationRepository(session).enqueue(
            organization_public_id="ORG-0001",
            seed=NotificationSeed(
                recipient_public_id="USR-0001",
                kind=NotificationKind.SLA_RISK,
                title="Case response limit needs attention",
                message="Case CS-2048 needs attention.",
                resource_type=NotificationResourceType.CASE,
                resource_public_id="CS-2048",
                event_key="test:sla:CS-2048",
            ),
        )


def test_quality_notifications_and_settings_are_tenant_scoped_and_versioned(
    database: Database,
    test_database_url: str,
) -> None:
    _seed(database)
    app = create_app(
        Settings(environment="test", database_url=test_database_url, _env_file=None)
    )

    with TestClient(app) as client:
        quality = client.get("/api/quality", headers=SUPERVISOR)
        notifications = client.get("/api/notifications", headers=SPECIALIST)
        settings = client.get("/api/settings/approvals", headers=ADMIN)
        updated = client.put(
            "/api/settings/approvals",
            headers=ADMIN,
            json={
                "section": "approvals",
                "expected_version": 1,
                "configuration": {
                    "administrator_financial_limits": {
                        "USD": "500.00",
                        "IDR": "7500000.00",
                    },
                    "require_decision_reason": True,
                },
            },
        )
        stale = client.put(
            "/api/settings/approvals",
            headers=ADMIN,
            json={
                "section": "approvals",
                "expected_version": 1,
                "configuration": {
                    "administrator_financial_limits": {"USD": "600.00"},
                    "require_decision_reason": True,
                },
            },
        )

    assert quality.status_code == 200
    assert quality.json()["data"]["total"] == 3
    assert len(quality.json()["data"]["metrics"]) == 4
    assert notifications.status_code == 200
    assert notifications.json()["unread_count"] == 1
    assert notifications.json()["items"][0]["resource_id"] == "CS-2048"
    assert settings.status_code == 200
    assert settings.json()["data"]["version"] == 1
    assert updated.status_code == 200
    assert updated.json()["data"]["settings"]["version"] == 2
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"


def test_member_safeguards_and_case_audit_export_are_enforced(
    database: Database,
    test_database_url: str,
) -> None:
    _seed(database)
    app = create_app(
        Settings(environment="test", database_url=test_database_url, _env_file=None)
    )

    with TestClient(app) as client:
        changed = client.patch(
            "/api/members/USR-0001",
            headers=ADMIN,
            json={"expected_version": 1, "role": "supervisor"},
        )
        self_change = client.patch(
            "/api/members/USR-0003",
            headers=ADMIN,
            json={"expected_version": 1, "status": "deactivated"},
        )
        auditor_case = client.get("/api/cases/CS-2048", headers=AUDITOR)
        audit = client.post(
            "/api/cases/CS-2048/audit-export",
            headers=AUDITOR,
        )

    assert changed.status_code == 200
    assert changed.json()["data"]["role"] == "supervisor"
    assert changed.json()["data"]["version"] == 2
    assert self_change.status_code == 409
    assert self_change.json()["error"]["code"] == "member_conflict"
    assert auditor_case.status_code == 200
    assert auditor_case.json()["data"]["available_commands"] == ["export_audit"]
    assert audit.status_code == 200
    assert audit.json()["data"]["case_id"] == "CS-2048"
    assert audit.json()["data"]["organization_id"] == "ORG-0001"
    assert any(
        event["event_type"] == "case.audit_exported"
        for event in audit.json()["data"]["events"]
    )
