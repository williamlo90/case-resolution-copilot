from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    AuthenticationMode,
    MemberRole,
)
from app.integrations.case_source_simulator import (
    DeterministicCaseSourceSimulator,
)
from app.integrations.policy_source_simulator import (
    DeterministicPolicySourceSimulator,
)
from app.main import create_app
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.models import (
    CaseProposalModel,
    CaseReviewDecisionModel,
    CaseReviewModel,
    CaseReviewReservationModel,
    CaseReviewSnapshotModel,
    MembershipModel,
    OrganizationModel,
)
from app.security.authentication import (
    DETERMINISTIC_ACTORS,
    DeterministicAuthProvider,
)

ADMIN = {"X-Actor-ID": "USR-0003"}
SPECIALIST = {"X-Actor-ID": "USR-0001"}
SUPERVISOR = {"X-Actor-ID": "USR-0002"}
OTHER_ADMIN = {"X-Actor-ID": "USR-9001"}


def _seed_workspace(database: Database) -> None:
    with database.session() as session:
        primary = OrganizationModel(
            public_id="ORG-0001",
            name="Northstar Cloud",
            slug="northstar-cloud",
        )
        other = OrganizationModel(
            public_id="ORG-0002",
            name="Other Organization",
            slug="other-organization",
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
                    public_id="USR-0002",
                    organization_id=primary.id,
                    subject_id="USR-0002",
                    name="Rina Supervisor",
                    email="rina.supervisor@example.com",
                    role="supervisor",
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
                correlation_id=f"review-test-seed:{command.public_id}",
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


def _publish_refund_policy(client: TestClient) -> None:
    seed = DeterministicPolicySourceSimulator().fetch_policies()[0]
    created = client.post(
        "/api/policies",
        headers=ADMIN,
        json={
            "public_id": seed.public_id,
            "title": seed.title,
            "description": seed.description,
            "source": {
                "kind": seed.source_kind.value,
                "name": seed.source_name,
            },
            "source_text": seed.source_text,
            "applicability": seed.applicability.model_dump(mode="json"),
            "effective_from": seed.effective_from.isoformat(),
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    draft = _version(created_body)
    submitted = client.post(
        f"/api/policies/{seed.public_id}/versions/1/submit-review",
        headers=ADMIN,
        json={
            "expected_policy_version": created_body["data"]["policy"]["version"],
            "expected_version": draft["record_version"],
        },
    )
    assert submitted.status_code == 200
    submitted_body = submitted.json()
    reviewed = _version(submitted_body)
    published = client.post(
        f"/api/policies/{seed.public_id}/versions/1/publish",
        headers=ADMIN,
        json={
            "expected_policy_version": submitted_body["data"]["policy"]["version"],
            "expected_version": reviewed["record_version"],
            "effective_from": seed.effective_from.isoformat(),
        },
    )
    assert published.status_code == 200


def test_case_review_is_snapshot_bound_authoritative_and_tenant_scoped(
    database: Database,
    test_database_url: str,
) -> None:
    _seed_workspace(database)
    app = create_app(
        Settings(
            environment="test",
            database_url=test_database_url,
            _env_file=None,
        )
    )
    app.state.auth_provider = DeterministicAuthProvider(
        {**DETERMINISTIC_ACTORS, "USR-9001": _other_actor()}
    )

    with TestClient(app) as client:
        _publish_refund_policy(client)
        generated = client.post(
            "/api/cases/CS-2047/proposals",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        assert generated.status_code == 201

        submitted = client.post(
            "/api/cases/CS-2047/proposals/1/reviews",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        repeated = client.post(
            "/api/cases/CS-2047/proposals/1/reviews",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        assert submitted.status_code == 201
        review = submitted.json()["data"]
        review_id = review["review"]["id"]
        fingerprint = review["review"]["snapshot_fingerprint"]

        specialist_reserve = client.post(
            f"/api/reviews/{review_id}/reserve",
            headers=SPECIALIST,
            json={"expected_version": 1},
        )
        self_review = client.post(
            f"/api/reviews/{review_id}/reserve",
            headers=SUPERVISOR,
            json={"expected_version": 1},
        )
        reserved = client.post(
            f"/api/reviews/{review_id}/reserve",
            headers=ADMIN,
            json={"expected_version": 1},
        )
        with database.session() as session:
            administrator = session.scalar(
                select(MembershipModel).where(MembershipModel.public_id == "USR-0003")
            )
            assert administrator is not None
            administrator.role = "specialist"
        demoted_decision = client.post(
            f"/api/reviews/{review_id}/decisions",
            headers=ADMIN,
            json={
                "expected_version": 2,
                "snapshot_fingerprint": fingerprint,
                "decision": "approve",
                "reason": "A stale administrator context must not grant authority.",
            },
        )
        with database.session() as session:
            administrator = session.scalar(
                select(MembershipModel).where(MembershipModel.public_id == "USR-0003")
            )
            assert administrator is not None
            administrator.role = "administrator"
        competing = client.post(
            f"/api/reviews/{review_id}/reserve",
            headers=SUPERVISOR,
            json={"expected_version": 2},
        )
        wrong_snapshot = client.post(
            f"/api/reviews/{review_id}/decisions",
            headers=ADMIN,
            json={
                "expected_version": 2,
                "snapshot_fingerprint": "f" * 64,
                "decision": "approve",
                "reason": "The wrong snapshot must not be accepted.",
            },
        )
        approved = client.post(
            f"/api/reviews/{review_id}/decisions",
            headers=ADMIN,
            json={
                "expected_version": 2,
                "snapshot_fingerprint": fingerprint,
                "decision": "approve",
                "reason": "Evidence, context, and proposed outcome were verified.",
            },
        )
        duplicate_decision = client.post(
            f"/api/reviews/{review_id}/decisions",
            headers=ADMIN,
            json={
                "expected_version": 3,
                "snapshot_fingerprint": fingerprint,
                "decision": "approve",
                "reason": "A second decision must not be recorded.",
            },
        )
        queue = client.get(
            "/api/reviews?status=approved",
            headers=SPECIALIST,
        )
        hidden = client.get(
            f"/api/reviews/{review_id}",
            headers=OTHER_ADMIN,
        )
        changed_case = client.post(
            "/api/cases/CS-2047/assign",
            headers=SPECIALIST,
            json={"expected_version": 2},
        )
        stale_detail = client.get(
            f"/api/reviews/{review_id}",
            headers=SUPERVISOR,
        )

    assert repeated.json()["data"]["review"]["id"] == review_id
    assert review["review"]["status"] == "pending"
    assert review["case_version"] == 2
    assert review["review"]["snapshot_freshness"]["status"] == "current"
    assert "approve" in review["available_decisions"]
    assert specialist_reserve.status_code == 403
    assert self_review.status_code == 409
    assert "different person" in self_review.json()["error"]["message"]
    assert reserved.status_code == 200
    assert reserved.json()["data"]["review"]["status"] == "reserved"
    assert demoted_decision.status_code == 403
    assert competing.status_code == 409
    assert wrong_snapshot.status_code == 409
    assert approved.status_code == 200
    approved_body = approved.json()["data"]
    assert approved_body["review"]["status"] == "approved"
    assert approved_body["available_decisions"] == []
    assert approved_body["decision_history"][0]["decision"] == "approve"
    assert approved_body["decision_history"][0]["snapshot_fingerprint"] == fingerprint
    assert duplicate_decision.status_code == 409
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    assert hidden.status_code == 404
    assert changed_case.status_code == 200
    assert stale_detail.status_code == 200
    assert stale_detail.json()["data"]["review"]["snapshot_freshness"]["status"] == "stale"

    with database.session() as session:
        snapshot = session.scalar(select(CaseReviewSnapshotModel))
        proposal = session.scalar(select(CaseProposalModel))

        assert snapshot is not None
        assert snapshot.execution_eligible
        assert proposal is not None
        assert proposal.state == "approved"
        assert session.scalar(select(func.count(CaseReviewModel.id))) == 1
        assert session.scalar(select(func.count(CaseReviewSnapshotModel.id))) == 1
        assert session.scalar(select(func.count(CaseReviewReservationModel.id))) == 1
        assert session.scalar(select(func.count(CaseReviewDecisionModel.id))) == 1
