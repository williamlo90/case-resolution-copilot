from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    AuthenticationMode,
    MemberRole,
)
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator
from app.main import create_app
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.models import (
    CasePolicyEvidenceModel,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    MembershipModel,
    OrganizationModel,
    PolicyModel,
)
from app.security.authentication import DETERMINISTIC_ACTORS, DeterministicAuthProvider

ADMIN = {"X-Actor-ID": "USR-0003"}
SPECIALIST = {"X-Actor-ID": "USR-0001"}
OTHER_ADMIN = {"X-Actor-ID": "USR-9001"}


def _seed_policy_workspace(database: Database) -> None:
    with database.session() as session:
        primary = OrganizationModel(
            public_id="ORG-0001", name="Northstar Cloud", slug="northstar-cloud"
        )
        other = OrganizationModel(
            public_id="ORG-0002", name="Other Organization", slug="other-organization"
        )
        session.add_all([primary, other])
        session.flush()
        session.add_all(
            [
                MembershipModel(
                    public_id="USR-0001",
                    organization_id=primary.id,
                    subject_id="USR-0001",
                    name="Maya Specialist",
                    email="maya.specialist@example.com",
                    role="specialist",
                    status="active",
                ),
                MembershipModel(
                    public_id="USR-0003",
                    organization_id=primary.id,
                    subject_id="USR-0003",
                    name="Ari Administrator",
                    email="ari.administrator@example.com",
                    role="administrator",
                    status="active",
                ),
                MembershipModel(
                    public_id="USR-9001",
                    organization_id=other.id,
                    subject_id="USR-9001",
                    name="Other Administrator",
                    email="other.administrator@example.com",
                    role="administrator",
                    status="active",
                ),
            ]
        )
        repository = CaseRepository(session)
        for command in DeterministicCaseSourceSimulator().fetch_cases():
            repository.seed_case(
                organization_public_id="ORG-0001",
                command=command,
                correlation_id=f"policy-test-seed:{command.public_id}",
            )


def _other_actor() -> ActorContext:
    role = MemberRole.ADMINISTRATOR
    return ActorContext(
        actor_id="USR-9001",
        organization_id="ORG-0002",
        name="Other Administrator",
        kind=ActorKind.MEMBER,
        role=role,
        permissions=ROLE_PERMISSIONS[role],
        authentication_mode=AuthenticationMode.DETERMINISTIC_DEVELOPMENT,
    )


def _version(response: dict[str, object], number: int = 1) -> dict[str, object]:
    versions = response["data"]["versions"]  # type: ignore[index]
    assert isinstance(versions, list)
    matches = [
        version
        for version in versions
        if isinstance(version, dict) and version.get("version") == number
    ]
    assert len(matches) == 1
    return matches[0]


def test_governed_policy_lifecycle_and_evidence_are_tenant_scoped(
    database: Database, test_database_url: str
) -> None:
    _seed_policy_workspace(database)
    app = create_app(Settings(environment="test", database_url=test_database_url, _env_file=None))
    app.state.auth_provider = DeterministicAuthProvider(
        {**DETERMINISTIC_ACTORS, "USR-9001": _other_actor()}
    )
    policy_payload = {
        "public_id": "POL-TEST-BILLING",
        "title": "Duplicate charge decisions",
        "description": "Controlled resolution rules for verified duplicate invoice charges.",
        "source": {"kind": "manual", "name": "Integration test policy"},
        "source_text": (
            "## Duplicate invoice charge\n"
            "A verified duplicate invoice charge may be reversed after both payment "
            "references are confirmed.\n\n"
            "## Specialist boundary\n"
            "A specialist must escalate the decision when payment evidence is incomplete."
        ),
        "applicability": {
            "decision_scope": "billing_adjustment",
            "case_categories": ["billing_dispute"],
            "products": ["all"],
            "regions": ["all"],
            "channels": ["all"],
            "customer_tiers": ["all"],
        },
        "effective_from": "2026-01-01T00:00:00Z",
    }

    with TestClient(app) as client:
        created = client.post("/api/policies", headers=ADMIN, json=policy_payload)
        assert created.status_code == 201
        created_body = created.json()
        created_version = _version(created_body)

        submitted = client.post(
            "/api/policies/POL-TEST-BILLING/versions/1/submit-review",
            headers=ADMIN,
            json={
                "expected_policy_version": created_body["data"]["policy"]["version"],
                "expected_version": created_version["record_version"],
            },
        )
        assert submitted.status_code == 200
        submitted_body = submitted.json()
        submitted_version = _version(submitted_body)

        stale = client.post(
            "/api/policies/POL-TEST-BILLING/versions/1/publish",
            headers=ADMIN,
            json={
                "expected_policy_version": created_body["data"]["policy"]["version"],
                "expected_version": submitted_version["record_version"],
                "effective_from": "2026-01-01T00:00:00Z",
            },
        )
        published = client.post(
            "/api/policies/POL-TEST-BILLING/versions/1/publish",
            headers=ADMIN,
            json={
                "expected_policy_version": submitted_body["data"]["policy"]["version"],
                "expected_version": submitted_version["record_version"],
                "effective_from": "2026-01-01T00:00:00Z",
            },
        )
        evidence = client.post(
            "/api/cases/CS-2048/policy-evidence/refresh",
            headers=SPECIALIST,
        )
        recorded = client.get("/api/cases/CS-2048/policy-evidence", headers=SPECIALIST)
        hidden_policy = client.get("/api/policies/POL-TEST-BILLING", headers=OTHER_ADMIN)
        hidden_case = client.post(
            "/api/cases/CS-2048/policy-evidence/refresh",
            headers=OTHER_ADMIN,
        )
        second_draft = client.post(
            "/api/policies/POL-TEST-BILLING/versions",
            headers=ADMIN,
            json={
                "expected_policy_version": published.json()["data"]["policy"]["version"],
                "source_text": policy_payload["source_text"],
                "applicability": policy_payload["applicability"],
                "effective_from": "2026-01-01T00:00:00Z",
            },
        )
        assert second_draft.status_code == 201
        second_draft_body = second_draft.json()
        second_draft_version = _version(second_draft_body, 2)
        second_review = client.post(
            "/api/policies/POL-TEST-BILLING/versions/2/submit-review",
            headers=ADMIN,
            json={
                "expected_policy_version": second_draft_body["data"]["policy"]["version"],
                "expected_version": second_draft_version["record_version"],
            },
        )
        assert second_review.status_code == 200
        second_review_body = second_review.json()
        second_review_version = _version(second_review_body, 2)
        scheduled = client.post(
            "/api/policies/POL-TEST-BILLING/versions/2/schedule",
            headers=ADMIN,
            json={
                "expected_policy_version": second_review_body["data"]["policy"]["version"],
                "expected_version": second_review_version["record_version"],
                "effective_from": "2099-01-01T00:00:00Z",
            },
        )
        assert scheduled.status_code == 200
        scheduled_body = scheduled.json()
        scheduled_version = _version(scheduled_body, 2)
        cancelled = client.post(
            "/api/policies/POL-TEST-BILLING/versions/2/retire",
            headers=ADMIN,
            json={
                "expected_policy_version": scheduled_body["data"]["policy"]["version"],
                "expected_version": scheduled_version["record_version"],
            },
        )
        assert cancelled.status_code == 200
        cancelled_body = cancelled.json()
        replacement = client.post(
            "/api/policies/POL-TEST-BILLING/versions",
            headers=ADMIN,
            json={
                "expected_policy_version": cancelled_body["data"]["policy"]["version"],
                "source_text": policy_payload["source_text"],
                "applicability": policy_payload["applicability"],
                "effective_from": "2026-01-01T00:00:00Z",
            },
        )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"
    assert published.status_code == 200
    published_version = _version(published.json())
    assert published.json()["data"]["policy"]["status"] == "published"
    assert published_version["status"] == "published"
    assert published_version["immutable"] is True
    assert evidence.status_code == 200
    assert evidence.json()["data"]["status"] == "relevant"
    assert len(evidence.json()["data"]["evidence"]) == 1
    assert recorded.json() == evidence.json()
    assert hidden_policy.status_code == 404
    assert hidden_case.status_code == 404
    assert cancelled_body["data"]["policy"]["status"] == "published"
    assert cancelled_body["data"]["policy"]["current_version"] == 1
    assert _version(cancelled_body, 2)["effective_to"] is None
    assert replacement.status_code == 201
    assert replacement.json()["data"]["policy"]["current_version"] == 3
    assert _version(replacement.json(), 3)["status"] == "draft"

    with database.session() as session:
        policy = session.scalar(
            select(PolicyModel).where(PolicyModel.public_id == "POL-TEST-BILLING")
        )
        version = session.scalar(
            select(GovernedPolicyVersionModel).where(
                GovernedPolicyVersionModel.public_id == published_version["id"]
            )
        )
        citation = session.scalar(select(CasePolicyEvidenceModel))
        assert policy is not None
        assert version is not None
        assert citation is not None
        clause = session.get(GovernedPolicyClauseModel, citation.clause_id)
        assert clause is not None
        assert policy.organization_id == version.organization_id == citation.organization_id
        assert version.id == citation.policy_version_id
        assert version.immutable is True
        assert version.effective_from == datetime(2026, 1, 1, tzinfo=UTC)
        assert citation.policy_content_hash == version.content_hash
        assert citation.clause_content_hash == clause.content_hash
        assert citation.fingerprint == evidence.json()["data"]["evidence"][0]["fingerprint"]
