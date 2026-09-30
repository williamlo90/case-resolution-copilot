from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.analysis.deterministic_decision_engine import DeterministicDecisionEngine
from app.config import Settings
from app.domain.cases import CaseCreate, CaseStatus, CaseWorkspaceRecord
from app.domain.decision_briefs import (
    DecisionAnalysis,
    DecisionGenerationInProgress,
    DecisionGenerationLease,
)
from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    AuthenticationMode,
    MemberRole,
)
from app.domain.policies import EvidenceRetrievalResult
from app.evaluation.case_resolution.validation import (
    load_frozen_case_resolution_benchmark,
)
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator
from app.integrations.policy_source_simulator import DeterministicPolicySourceSimulator
from app.main import create_app
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.decision_generation_repository import DecisionGenerationRepository
from app.persistence.models import (
    CaseAnalysisCheckpointModel,
    CaseAnalysisGenerationModel,
    CaseAnalysisRunModel,
    CaseModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    GovernedPolicyVersionModel,
    MembershipModel,
    OrganizationModel,
    ProposalContextBindingModel,
    ProposalEvidenceBindingModel,
)
from app.security.authentication import DETERMINISTIC_ACTORS, DeterministicAuthProvider

ADMIN = {"X-Actor-ID": "USR-0003"}
SPECIALIST = {"X-Actor-ID": "USR-0001"}
OTHER_ADMIN = {"X-Actor-ID": "USR-9001"}


def _seed_workspace(database: Database) -> None:
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
                correlation_id=f"decision-test-seed:{command.public_id}",
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


def _publish_policy(client: TestClient, policy_id: str) -> None:
    seed = next(
        item
        for item in DeterministicPolicySourceSimulator().fetch_policies()
        if item.public_id == policy_id
    )
    created = client.post(
        "/api/policies",
        headers=ADMIN,
        json={
            "public_id": seed.public_id,
            "title": seed.title,
            "description": seed.description,
            "source": {"kind": seed.source_kind.value, "name": seed.source_name},
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


def _publish_refund_policy(client: TestClient) -> None:
    _publish_policy(client, "POL-1008")


def _seed_conflicting_account_case(database: Database) -> None:
    benchmark_root = Path(__file__).resolve().parents[2] / "evaluations" / "case_resolution_v1"
    benchmark = load_frozen_case_resolution_benchmark(benchmark_root)
    fixture = next(case for case in benchmark.inputs.cases if case.case_id == "CRV1-006")
    command = CaseCreate.model_validate(
        {
            "public_id": fixture.public_case_id,
            "source_id": "case-resolution-evaluation-v1:CRV1-006",
            "external_reference": fixture.external_reference,
            "category": fixture.category,
            "issue": fixture.request_summary,
            "status": CaseStatus.INVESTIGATING,
            "urgency": fixture.urgency,
            "risk": fixture.risk,
            "due_at": fixture.as_of + timedelta(days=1),
            "impact_amount": fixture.impact_amount,
            "impact_currency": fixture.impact_currency,
            "source_freshness": fixture.source_freshness,
            "source_checked_at": fixture.source_checked_at,
            "request": {
                "channel": fixture.channel,
                "customer_message": fixture.customer_request,
                "summary": fixture.request_summary,
                "received_at": fixture.as_of,
            },
            "customer": {
                "customer_id": "CUS-CRV1-006",
                "name": "Evaluation Customer CRV1-006",
                "tier": fixture.customer_tier,
                "locale": "en-US",
                "contact": "crv1-006@example.invalid",
            },
            "business_contexts": [
                {
                    "public_id": evidence.public_id,
                    "type": evidence.type,
                    "label": evidence.label,
                    "source": evidence.source,
                    "source_reference": evidence.source_reference,
                    "status": evidence.status,
                    "fields": evidence.fields,
                    "captured_at": evidence.captured_at,
                    "freshness": evidence.source_freshness,
                    "checked_at": evidence.source_checked_at,
                }
                for evidence in fixture.available_evidence
            ],
        }
    )
    with database.session() as session:
        CaseRepository(session).seed_case(
            organization_public_id="ORG-0001",
            command=command,
            correlation_id="case-resolution-evaluation-v1:CRV1-006",
        )


def test_decision_briefs_are_idempotent_versioned_and_tenant_scoped(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    app = create_app(Settings(environment="test", database_url=test_database_url, _env_file=None))
    app.state.auth_provider = DeterministicAuthProvider(
        {**DETERMINISTIC_ACTORS, "USR-9001": _other_actor()}
    )

    with TestClient(app) as client:
        _publish_refund_policy(client)
        generated = client.post(
            "/api/cases/CS-2047/proposals",
            headers=SPECIALIST,
            json={"expected_case_version": 1},
        )
        repeated = client.post(
            "/api/cases/CS-2047/proposals",
            headers=SPECIALIST,
            json={"expected_case_version": 1},
        )
        current = client.get(
            "/api/cases/CS-2047/proposals/current",
            headers=SPECIALIST,
        )
        case_workspace = client.get("/api/cases/CS-2047", headers=SPECIALIST)
        assigned = client.post(
            "/api/cases/CS-2047/assign",
            headers=SPECIALIST,
            json={"expected_version": 1},
        )
        stale = client.post(
            "/api/cases/CS-2047/proposals",
            headers=SPECIALIST,
            json={"expected_case_version": 1},
        )
        revised = client.post(
            "/api/cases/CS-2047/proposals",
            headers=SPECIALIST,
            json={"expected_case_version": 2},
        )
        first_version = client.get(
            "/api/cases/CS-2047/proposals/1",
            headers=SPECIALIST,
        )
        hidden = client.get(
            "/api/cases/CS-2047/proposals/current",
            headers=OTHER_ADMIN,
        )

    assert generated.status_code == 201
    generated_body = generated.json()["data"]
    assert generated_body["analysis"]["status"] == "completed"
    assert generated_body["analysis"]["policy_status"] == "relevant"
    assert generated_body["proposal"]["state"] == "ready_for_review"
    assert generated_body["proposal"]["version"] == 1
    assert generated_body["proposal"]["impact"] == {
        "amount": "125.00",
        "currency": "USD",
    }
    assert generated_body["proposal"]["evidence_ids"]
    assert generated_body["facts"]
    assert generated_body["risks"]
    assert generated_body["proposed_actions"][0]["type"] == "issue_refund"
    assert generated_body["response_draft"]["status"] == "ready"
    assert len(generated_body["checkpoints"]) == 4
    assert repeated.json()["data"]["analysis"]["id"] == generated_body["analysis"]["id"]
    assert repeated.json()["data"]["proposal"]["version"] == 1
    assert current.json()["data"]["proposal"] == generated_body["proposal"]
    assert case_workspace.json()["data"]["proposal"] == generated_body["proposal"]
    assert assigned.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"
    assert revised.status_code == 201
    assert revised.json()["data"]["proposal"]["version"] == 2
    assert revised.json()["data"]["analysis"]["id"] != generated_body["analysis"]["id"]
    assert first_version.json()["data"]["proposal"]["version"] == 1
    assert hidden.status_code == 404

    with database.session() as session:
        proposal = session.scalar(select(CaseProposalModel))
        versions = list(
            session.scalars(
                select(CaseProposalVersionModel).order_by(CaseProposalVersionModel.version)
            )
        )
        run_count = session.scalar(select(func.count(CaseAnalysisRunModel.id)))
        checkpoint_count = session.scalar(select(func.count(CaseAnalysisCheckpointModel.id)))
        evidence_binding_count = session.scalar(select(func.count(ProposalEvidenceBindingModel.id)))
        context_binding_count = session.scalar(select(func.count(ProposalContextBindingModel.id)))

        assert proposal is not None
        assert proposal.current_version == 2
        assert proposal.version == 2
        assert [version.version for version in versions] == [1, 2]
        assert all(version.immutable for version in versions)
        assert run_count == 2
        assert checkpoint_count == 8
        assert evidence_binding_count == 2
        assert context_binding_count == 2


def test_conflicting_ownership_is_persisted_fail_closed_and_cannot_enter_review(
    database: Database,
    test_database_url: str,
) -> None:
    _seed_workspace(database)
    _seed_conflicting_account_case(database)
    app = create_app(
        Settings(environment="test", database_url=test_database_url, _env_file=None)
    )

    with TestClient(app) as client:
        _publish_policy(client, "POL-1007")
        generated = client.post(
            "/api/cases/CS-EVAL-006/proposals",
            headers=SPECIALIST,
            json={"expected_case_version": 1},
        )
        submitted = client.post(
            "/api/cases/CS-EVAL-006/proposals/1/reviews",
            headers=SPECIALIST,
            json={"expected_case_version": 1},
        )

    assert generated.status_code == 201
    detail = generated.json()["data"]
    assert detail["analysis"]["model_version"] == "deterministic-decision-engine-v3"
    assert detail["proposal"]["state"] == "information_needed"
    assert detail["proposal"]["outcome"] == (
        "Escalate conflicting ownership evidence before account recovery"
    )
    assert {item["label"] for item in detail["missing_information"]} == {
        "Identity verification"
    }
    assert [item["type"] for item in detail["proposed_actions"]] == [
        "request_information"
    ]
    assert detail["response_draft"]["status"] == "blocked"
    assert submitted.status_code == 409
    assert submitted.json()["error"]["code"] == "review_submission_not_allowed"

    with database.session() as session:
        proposal = session.scalar(
            select(CaseProposalModel)
            .join(CaseModel, CaseModel.id == CaseProposalModel.case_id)
            .where(CaseModel.public_id == "CS-EVAL-006")
        )
        assert proposal is not None
        assert proposal.state == "information_needed"


def test_generation_reservation_is_single_flight_under_bounded_concurrency(
    database: Database,
) -> None:
    _seed_workspace(database)
    provider_calls = 0
    counter_lock = Lock()
    input_fingerprint = "a" * 64

    def contender() -> str:
        nonlocal provider_calls
        try:
            with database.session() as session:
                DecisionGenerationRepository(session).acquire(
                    organization_public_id="ORG-0001",
                    case_public_id="CS-2047",
                    input_fingerprint=input_fingerprint,
                    lease_seconds=60,
                    max_attempts=3,
                )
            with counter_lock:
                provider_calls += 1
            return "acquired"
        except DecisionGenerationInProgress:
            return "in_progress"

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: contender(), range(20)))

    assert results.count("acquired") == 1
    assert results.count("in_progress") == 19
    assert provider_calls == 1
    with database.session() as session:
        assert (
            session.scalar(select(func.count(CaseAnalysisGenerationModel.id))) == 1
        )


def test_expired_generation_lease_uses_fencing_tokens(database: Database) -> None:
    _seed_workspace(database)
    input_fingerprint = "b" * 64
    with database.session() as session:
        first = DecisionGenerationRepository(session).acquire(
            organization_public_id="ORG-0001",
            case_public_id="CS-2047",
            input_fingerprint=input_fingerprint,
            lease_seconds=60,
            max_attempts=3,
        )
    with database.session() as session:
        row = session.scalar(select(CaseAnalysisGenerationModel))
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with database.session() as session:
        second = DecisionGenerationRepository(session).acquire(
            organization_public_id="ORG-0001",
            case_public_id="CS-2047",
            input_fingerprint=input_fingerprint,
            lease_seconds=60,
            max_attempts=3,
        )

    assert isinstance(first, DecisionGenerationLease)
    assert isinstance(second, DecisionGenerationLease)
    assert second.owner_token != first.owner_token
    assert second.fence_token == first.fence_token + 1
    with database.session() as session:
        repository = DecisionGenerationRepository(session)
        assert (
            repository.fail(
                organization_public_id="ORG-0001",
                case_public_id="CS-2047",
                lease=first,
                error_code="late_worker",
            )
            is False
        )
        assert (
            repository.fail(
                organization_public_id="ORG-0001",
                case_public_id="CS-2047",
                lease=second,
                error_code="provider_failure",
            )
            is True
        )


def test_policy_change_during_inference_rejects_stale_model_output(
    database: Database,
    test_database_url: str,
) -> None:
    _seed_workspace(database)

    class RetiringPolicyEngine(DeterministicDecisionEngine):
        def analyze(
            self,
            *,
            workspace: CaseWorkspaceRecord,
            evidence: EvidenceRetrievalResult,
            input_fingerprint: str,
        ) -> DecisionAnalysis:
            with database.session() as session:
                version = session.scalar(
                    select(GovernedPolicyVersionModel).where(
                        GovernedPolicyVersionModel.status == "published"
                    )
                )
                assert version is not None
                version.status = "retired"
                version.retired_at = datetime.now(UTC)
            return super().analyze(
                workspace=workspace,
                evidence=evidence,
                input_fingerprint=input_fingerprint,
            )

    app = create_app(
        Settings(environment="test", database_url=test_database_url, _env_file=None)
    )
    app.state.decision_engine = RetiringPolicyEngine()
    with TestClient(app) as client:
        _publish_refund_policy(client)
        generated = client.post(
            "/api/cases/CS-2047/proposals",
            headers=SPECIALIST,
            json={"expected_case_version": 1},
        )

    assert generated.status_code == 409
    assert generated.json()["error"]["code"] == "proposal_snapshot_changed"
    with database.session() as session:
        assert session.scalar(select(func.count(CaseAnalysisRunModel.id))) == 0
        reservation = session.scalar(select(CaseAnalysisGenerationModel))
        assert reservation is not None
        assert reservation.status == "failed"
