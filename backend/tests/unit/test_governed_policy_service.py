from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.domain.cases import (
    BusinessObjectRecord,
    BusinessObjectType,
    CaseCategory,
    CaseCollectionWindowRecord,
    CaseRecord,
    CaseRequestRecord,
    CaseRisk,
    CaseStatus,
    CaseUrgency,
    CaseWorkspaceCollectionsRecord,
    CaseWorkspaceRecord,
    ConversationThreadRecord,
    CustomerContextRecord,
    CustomerTier,
    RequestChannel,
    SourceFreshness,
)
from app.domain.policies import (
    CasePolicyEvidenceRecord,
    EvidenceRetrievalStatus,
    GovernedPolicyClauseRecord,
    GovernedPolicyVersionRecord,
    IndexedPolicyClause,
    InvalidPolicyTransition,
    PolicyApplicability,
    PolicyCandidateRecord,
    PolicyDraftContent,
    PolicyEvidenceBinding,
    PolicyEvidenceBundle,
    PolicyLifecycleStatus,
    PolicyOwnerRecord,
    PolicyRecord,
    PolicyRetrievalCandidatePage,
    PolicySourceKind,
    PolicyVersionBundle,
    PolicyVersionStatus,
    PolicyWorkspaceRecord,
    RankedPolicyCandidateRecord,
)
from app.retrieval.embeddings import EMBEDDING_VERSION, embed
from app.security.authentication import DeterministicAuthProvider
from app.security.authorization import PermissionDenied
from app.services.policy_evidence_service import (
    CaseEvidenceStore,
    PolicyEvidenceService,
    PolicyEvidenceStore,
)
from app.services.policy_service import (
    PolicyService,
    PolicyStore,
)

NOW = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)


def _policy_record(
    public_id: str,
    *,
    status: PolicyLifecycleStatus,
    policy_uuid: UUID | None = None,
) -> PolicyRecord:
    return PolicyRecord(
        id=policy_uuid or uuid4(),
        public_id=public_id,
        organization_id=uuid4(),
        title=f"Policy {public_id}",
        description="A governed policy used by deterministic service tests.",
        status=status,
        owner_id=uuid4(),
        source_kind=PolicySourceKind.MANUAL,
        source_name="Deterministic test source",
        source_error=None,
        current_version=1,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _version(
    policy: PolicyRecord,
    *,
    status: PolicyVersionStatus,
    decision_scope: str = "billing_adjustment",
    effective_from: datetime | None = NOW - timedelta(days=30),
) -> GovernedPolicyVersionRecord:
    return GovernedPolicyVersionRecord(
        id=uuid4(),
        public_id=f"POLV-{uuid4().hex[:12].upper()}",
        organization_id=policy.organization_id,
        policy_id=policy.id,
        legacy_policy_version_id=None,
        version=1,
        record_version=1,
        status=status,
        immutable=status
        in {
            PolicyVersionStatus.PUBLISHED,
            PolicyVersionStatus.SCHEDULED,
            PolicyVersionStatus.RETIRED,
        },
        source_text="A verified duplicate invoice charge may be corrected after review.",
        content_hash="a" * 64,
        decision_scope=decision_scope,
        case_categories=["billing_dispute"],
        products=["all"],
        regions=["all"],
        channels=["all"],
        customer_tiers=["all"],
        effective_from=effective_from,
        effective_to=None,
        created_by="USR-0003",
        created_at=NOW,
        submitted_at=NOW,
        published_at=NOW if status is PolicyVersionStatus.PUBLISHED else None,
        retired_at=None,
    )


def _clause(
    policy: PolicyRecord, version: GovernedPolicyVersionRecord
) -> GovernedPolicyClauseRecord:
    text = "A verified duplicate invoice charge may be corrected after invoice review."
    return GovernedPolicyClauseRecord(
        id=uuid4(),
        public_id=f"POLC-{uuid4().hex[:12].upper()}",
        organization_id=policy.organization_id,
        policy_id=policy.id,
        policy_version_id=version.id,
        sequence=1,
        heading="Duplicate charges",
        text=text,
        applies_when="Billing dispute cases.",
        content_hash="b" * 64,
        chunking_version="markdown-clause-v1",
        embedding_version=EMBEDDING_VERSION,
        index_version="governed-policy-index-v1",
        embedding=embed(text),
    )


def _workspace(
    *,
    policy_status: PolicyLifecycleStatus,
    version_status: PolicyVersionStatus,
) -> PolicyWorkspaceRecord:
    policy = _policy_record("POL-TEST", status=policy_status)
    version = _version(policy, status=version_status)
    return PolicyWorkspaceRecord(
        policy=policy,
        owner=PolicyOwnerRecord(id=uuid4(), public_id="USR-0003", name="Admin"),
        versions=[
            PolicyVersionBundle(version=version, clauses=[_clause(policy, version)], evidence=[])
        ],
    )


def _candidate(
    public_id: str,
    *,
    scope: str = "billing_adjustment",
    effective_from: datetime | None = NOW - timedelta(days=30),
) -> PolicyCandidateRecord:
    policy = _policy_record(public_id, status=PolicyLifecycleStatus.PUBLISHED)
    version = _version(
        policy,
        status=PolicyVersionStatus.PUBLISHED,
        decision_scope=scope,
        effective_from=effective_from,
    )
    return PolicyCandidateRecord(
        policy=policy,
        version=version,
        clauses=[_clause(policy, version)],
    )


class RecordingPolicyStore:
    def __init__(
        self,
        workspace: PolicyWorkspaceRecord,
        candidates: list[PolicyCandidateRecord] | None = None,
    ) -> None:
        self.workspace = workspace
        self.candidates = candidates or []
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_workspace(self, **values: object) -> PolicyWorkspaceRecord:
        self.calls.append(("get", values))
        return self.workspace

    def submit_review(self, **values: object) -> PolicyWorkspaceRecord:
        self.calls.append(("submit", values))
        return self.workspace

    def list_candidates(self, **values: object) -> list[PolicyCandidateRecord]:
        self.calls.append(("candidates", values))
        return self.candidates

    def mark_conflicting(self, **values: object) -> PolicyWorkspaceRecord:
        self.calls.append(("conflict", values))
        return self.workspace

    def activate_version(self, **values: object) -> PolicyWorkspaceRecord:
        self.calls.append(("activate", values))
        return self.workspace


class _RecordingEmbeddingProvider:
    version = "test-embedding-v1"
    dimensions = 32

    def __init__(self, events: list[str]) -> None:
        self._events = events

    def embed(self, text: str) -> list[float]:
        self._events.append("embed")
        return [0.125] * self.dimensions


class _TransactionBoundaryPolicyStore:
    def __init__(self, workspace: PolicyWorkspaceRecord, events: list[str]) -> None:
        self.workspace = workspace
        self.events = events
        self.indexed_clauses: list[IndexedPolicyClause] = []

    def get_workspace(self, **values: object) -> PolicyWorkspaceRecord:
        self.events.append("database_read")
        return self.workspace

    def create_draft(self, **values: object) -> PolicyWorkspaceRecord:
        self.events.append("database_write")
        clauses = values["clauses"]
        assert isinstance(clauses, list)
        self.indexed_clauses = [
            clause for clause in clauses if isinstance(clause, IndexedPolicyClause)
        ]
        return self.workspace


def test_policy_draft_embeddings_are_prepared_before_database_access() -> None:
    events: list[str] = []
    store = _TransactionBoundaryPolicyStore(
        _workspace(
            policy_status=PolicyLifecycleStatus.PUBLISHED,
            version_status=PolicyVersionStatus.PUBLISHED,
        ),
        events,
    )
    actor = DeterministicAuthProvider().authenticate("USR-0003")
    content = PolicyDraftContent(
        source_text=(
            "# Refund approval\n"
            "A verified duplicate charge may be refunded after supervisor review."
        ),
        applicability=PolicyApplicability(
            decision_scope="billing_adjustment",
            case_categories=["billing_dispute"],
            products=["all"],
            regions=["all"],
            channels=["all"],
            customer_tiers=["all"],
        ),
    )

    PolicyService(
        cast(PolicyStore, store),
        _RecordingEmbeddingProvider(events),
    ).create_draft(
        actor=actor,
        policy_id="POL-TEST",
        expected_policy_version=1,
        content=content,
        correlation_id="corr-test",
    )

    assert events == ["embed", "database_read", "database_write"]
    assert len(store.indexed_clauses) == 1
    assert store.indexed_clauses[0].embedding_version == "test-embedding-v1"


def test_admin_can_submit_current_draft_with_actor_tenant_scope() -> None:
    store = RecordingPolicyStore(
        _workspace(
            policy_status=PolicyLifecycleStatus.DRAFT,
            version_status=PolicyVersionStatus.DRAFT,
        )
    )
    actor = DeterministicAuthProvider().authenticate("USR-0003")

    PolicyService(cast(PolicyStore, store)).submit_review(
        actor=actor,
        policy_id="POL-TEST",
        version_number=1,
        expected_policy_version=1,
        expected_version=1,
        correlation_id="corr-test",
    )

    submit = next(values for name, values in store.calls if name == "submit")
    assert submit["organization_public_id"] == "ORG-0001"
    assert submit["actor_id"] == "USR-0003"


def test_specialist_cannot_manage_policy_lifecycle() -> None:
    store = RecordingPolicyStore(
        _workspace(
            policy_status=PolicyLifecycleStatus.DRAFT,
            version_status=PolicyVersionStatus.DRAFT,
        )
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(PermissionDenied):
        PolicyService(cast(PolicyStore, store)).submit_review(
            actor=actor,
            policy_id="POL-TEST",
            version_number=1,
            expected_policy_version=1,
            expected_version=1,
            correlation_id="corr-test",
        )

    assert store.calls == []


def test_future_publication_requires_schedule() -> None:
    store = RecordingPolicyStore(
        _workspace(
            policy_status=PolicyLifecycleStatus.IN_REVIEW,
            version_status=PolicyVersionStatus.IN_REVIEW,
        )
    )
    actor = DeterministicAuthProvider().authenticate("USR-0003")

    with pytest.raises(InvalidPolicyTransition, match="schedule"):
        PolicyService(cast(PolicyStore, store)).publish(
            actor=actor,
            policy_id="POL-TEST",
            version_number=1,
            expected_policy_version=1,
            expected_version=1,
            effective_from=NOW + timedelta(days=1),
            correlation_id="corr-test",
            now=NOW,
        )

    assert all(name != "activate" for name, _ in store.calls)


def test_overlapping_decision_scope_is_marked_conflicting() -> None:
    store = RecordingPolicyStore(
        _workspace(
            policy_status=PolicyLifecycleStatus.IN_REVIEW,
            version_status=PolicyVersionStatus.IN_REVIEW,
        ),
        candidates=[_candidate("POL-OTHER")],
    )
    actor = DeterministicAuthProvider().authenticate("USR-0003")

    PolicyService(cast(PolicyStore, store)).publish(
        actor=actor,
        policy_id="POL-TEST",
        version_number=1,
        expected_policy_version=1,
        expected_version=1,
        effective_from=NOW,
        correlation_id="corr-test",
        now=NOW,
    )

    conflict = next(values for name, values in store.calls if name == "conflict")
    assert conflict["conflicting_policy_ids"] == ["POL-OTHER"]
    assert all(name != "activate" for name, _ in store.calls)


def _case_workspace() -> CaseWorkspaceRecord:
    organization_id = uuid4()
    case_id = uuid4()
    request_id = uuid4()
    customer_id = uuid4()
    thread_id = uuid4()
    business_id = uuid4()
    return CaseWorkspaceRecord(
        case=CaseRecord(
            id=case_id,
            public_id="CS-2048",
            organization_id=organization_id,
            legacy_task_id=None,
            source_id="test-source",
            external_reference="INV-2048",
            category=CaseCategory.BILLING_DISPUTE,
            issue="Customer reports a duplicate invoice charge",
            status=CaseStatus.INVESTIGATING,
            owner_id=None,
            urgency=CaseUrgency.HIGH,
            risk=CaseRisk.MEDIUM,
            due_at=NOW + timedelta(hours=1),
            impact_amount=Decimal("100.00"),
            impact_currency="USD",
            source_freshness=SourceFreshness.CURRENT,
            source_checked_at=NOW,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        ),
        request=CaseRequestRecord(
            id=request_id,
            public_id="REQ-CS-2048",
            organization_id=organization_id,
            case_id=case_id,
            channel=RequestChannel.EMAIL,
            customer_message="I was charged twice for one invoice.",
            summary="Possible duplicate invoice charge.",
            received_at=NOW,
        ),
        customer=CustomerContextRecord(
            id=customer_id,
            organization_id=organization_id,
            case_id=case_id,
            customer_id="CUS-2048",
            name="Customer",
            tier=CustomerTier.VIP,
            locale="en-SG",
            contact="customer@example.com",
            captured_at=NOW,
        ),
        business_contexts=[
            BusinessObjectRecord(
                id=business_id,
                public_id="CTX-2048",
                organization_id=organization_id,
                case_id=case_id,
                type=BusinessObjectType.INVOICE,
                label="Invoice INV-2048",
                source="test",
                source_reference="INV-2048",
                status="paid",
                fields={"product": "billing_core"},
                captured_at=NOW,
                source_freshness=SourceFreshness.CURRENT,
                source_checked_at=NOW,
                version=1,
            )
        ],
        owner=None,
        thread=ConversationThreadRecord(
            id=thread_id,
            public_id="CV-CS-2048",
            organization_id=organization_id,
            case_id=case_id,
            version=1,
            updated_at=NOW,
        ),
        messages=[],
        draft=None,
        activity=[],
        collections=CaseWorkspaceCollectionsRecord(
            business_contexts=CaseCollectionWindowRecord(
                returned=1,
                total=1,
                has_more=False,
            ),
            messages=CaseCollectionWindowRecord(
                returned=0,
                total=0,
                has_more=False,
            ),
            activity=CaseCollectionWindowRecord(
                returned=0,
                total=0,
                has_more=False,
            ),
        ),
    )


class FixedCaseStore:
    def __init__(self, workspace: CaseWorkspaceRecord) -> None:
        self.workspace = workspace

    def get_workspace(self, **values: object) -> CaseWorkspaceRecord:
        del values
        return self.workspace


class EvidencePolicyStore:
    def __init__(
        self,
        candidates: list[PolicyCandidateRecord],
        *,
        retrieval_score: float = 0.9,
    ) -> None:
        self.candidates = candidates
        self.retrieval_score = retrieval_score
        self.bindings: list[PolicyEvidenceBinding] = []
        self.searches: list[dict[str, object]] = []

    def search_retrieval_candidates(
        self,
        **values: object,
    ) -> PolicyRetrievalCandidatePage:
        self.searches.append(values)
        category = str(values["case_category"])
        products = cast(set[str], values["products"])
        region = str(values["region"])
        channel = str(values["channel"])
        customer_tier = str(values["customer_tier"])
        as_of = cast(datetime, values["as_of"])
        candidate_limit = int(cast(int, values["candidate_limit"]))
        category_candidates = [
            item
            for item in self.candidates
            if _matches(item.version.case_categories, {category})
        ]
        applicable = [
            item
            for item in category_candidates
            if all(
                (
                    _matches(item.version.products, products),
                    _matches(item.version.regions, {region}),
                    _matches(item.version.channels, {channel}),
                    _matches(item.version.customer_tiers, {customer_tier}),
                )
            )
        ]
        active = [
            item
            for item in applicable
            if (item.version.effective_from is None or item.version.effective_from <= as_of)
            and (item.version.effective_to is None or as_of < item.version.effective_to)
        ]
        scopes: dict[str, set[str]] = {}
        for item in active:
            scopes.setdefault(item.version.decision_scope, set()).add(
                item.policy.public_id
            )
        conflicting_scopes = sorted(
            scope for scope, policies in scopes.items() if len(policies) > 1
        )
        return PolicyRetrievalCandidatePage(
            category_matches=len(category_candidates),
            applicable_matches=len(applicable),
            active_matches=len(active),
            truncated=False,
            conflicting_scopes=conflicting_scopes,
            candidates=[
                RankedPolicyCandidateRecord(
                    candidate=item,
                    retrieval_score=self.retrieval_score,
                )
                for item in active[:candidate_limit]
            ],
        )

    def bind_evidence(self, **values: object) -> list[PolicyEvidenceBundle]:
        bindings = cast(list[PolicyEvidenceBinding], values["bindings"])
        self.bindings.extend(bindings)
        return [self._bundle(binding) for binding in bindings]

    @staticmethod
    def _bundle(binding: PolicyEvidenceBinding) -> PolicyEvidenceBundle:
        return PolicyEvidenceBundle(
            evidence=CasePolicyEvidenceRecord(
                id=uuid4(),
                public_id=f"EVD-{uuid4().hex[:12].upper()}",
                organization_id=binding.policy.organization_id,
                case_id=uuid4(),
                policy_id=binding.policy.id,
                policy_version_id=binding.version.id,
                clause_id=binding.clause.id,
                citation=f"{binding.policy.title}, {binding.clause.heading}",
                excerpt=binding.clause.text,
                applicability=binding.applicability,
                fingerprint=binding.fingerprint,
                freshness="current",
                conflict_state="none",
                retrieval_score=binding.retrieval_score,
                policy_content_hash=binding.version.content_hash,
                clause_content_hash=binding.clause.content_hash,
                effective_from=binding.version.effective_from,
                effective_to=binding.version.effective_to,
                corpus_version="governed-policy-corpus-v1",
                chunking_version=binding.clause.chunking_version,
                embedding_version=binding.clause.embedding_version,
                index_version=binding.clause.index_version,
                recorded_at=NOW,
            ),
            policy=binding.policy,
            version=binding.version,
            clause=binding.clause,
        )


def _evidence_service(
    candidates: list[PolicyCandidateRecord],
    *,
    retrieval_score: float = 0.9,
) -> tuple[PolicyEvidenceService, EvidencePolicyStore]:
    policy_store = EvidencePolicyStore(
        candidates,
        retrieval_score=retrieval_score,
    )
    service = PolicyEvidenceService(
        cast(PolicyEvidenceStore, policy_store),
        cast(CaseEvidenceStore, FixedCaseStore(_case_workspace())),
    )
    return service, policy_store


def _matches(candidate_values: list[str], expected: set[str]) -> bool:
    values = set(candidate_values)
    return "all" in values or bool(values & expected)


def test_retrieval_records_only_applicable_published_evidence() -> None:
    service, store = _evidence_service([_candidate("POL-BILLING")])
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.refresh_for_case(
        actor=actor,
        case_id="CS-2048",
        correlation_id="corr-test",
        as_of=NOW,
    )

    assert result.status is EvidenceRetrievalStatus.RELEVANT
    assert len(result.evidence) == 1
    assert len(store.bindings) == 1


def test_retrieval_uses_bounded_lexical_fallback_when_vector_score_is_low() -> None:
    service, store = _evidence_service(
        [_candidate("POL-BILLING")],
        retrieval_score=0.01,
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.refresh_for_case(
        actor=actor,
        case_id="CS-2048",
        correlation_id="corr-test",
        as_of=NOW,
    )

    assert result.status is EvidenceRetrievalStatus.RELEVANT
    assert len(store.bindings) == 1
    assert store.bindings[0].retrieval_score > 0.01


def test_retrieval_prefers_matching_refund_clause_within_policy() -> None:
    candidate = _candidate("POL-BILLING")
    version = candidate.version.model_copy(
        update={"case_categories": [CaseCategory.REFUND_REQUEST.value]}
    )
    duplicate_clause = candidate.clauses[0].model_copy(
        update={"policy_version_id": version.id}
    )
    refund_text = (
        "An unused service order may be refunded when delivery has not started and no "
        "non-refundable commitment is recorded. Human review is required before execution."
    )
    refund_clause = duplicate_clause.model_copy(
        update={
            "id": uuid4(),
            "public_id": f"POLC-{uuid4().hex[:12].upper()}",
            "sequence": 2,
            "heading": "Refund eligibility",
            "text": refund_text,
            "applies_when": "Refund request cases.",
            "content_hash": "c" * 64,
            "embedding": embed(refund_text),
        }
    )
    candidates = [
        PolicyCandidateRecord(
            policy=candidate.policy,
            version=version,
            clauses=[duplicate_clause],
        ),
        PolicyCandidateRecord(
            policy=candidate.policy,
            version=version,
            clauses=[refund_clause],
        ),
    ]
    workspace = _case_workspace()
    workspace = workspace.model_copy(
        update={
            "case": workspace.case.model_copy(
                update={
                    "category": CaseCategory.REFUND_REQUEST,
                    "issue": "Enterprise customer requests a refund for an unused setup",
                }
            ),
            "request": workspace.request.model_copy(
                update={
                    "summary": "Refund request for an unused order before delivery started."
                }
            ),
        }
    )
    store = EvidencePolicyStore(candidates, retrieval_score=0.9)
    service = PolicyEvidenceService(
        cast(PolicyEvidenceStore, store),
        cast(CaseEvidenceStore, FixedCaseStore(workspace)),
    )

    result = service.refresh_for_case(
        actor=DeterministicAuthProvider().authenticate("USR-0001"),
        case_id="CS-2048",
        correlation_id="corr-refund-clause",
        as_of=NOW,
    )

    assert result.status is EvidenceRetrievalStatus.RELEVANT
    assert len(result.evidence) == 1
    assert result.evidence[0].clause.heading == "Refund eligibility"
    assert store.bindings[0].clause.public_id == refund_clause.public_id


def test_retrieval_reports_stale_without_recording_evidence() -> None:
    service, store = _evidence_service(
        [_candidate("POL-FUTURE", effective_from=NOW + timedelta(days=1))]
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.refresh_for_case(
        actor=actor,
        case_id="CS-2048",
        correlation_id="corr-test",
        as_of=NOW,
    )

    assert result.status is EvidenceRetrievalStatus.STALE
    assert result.evidence == []
    assert store.bindings == []


def test_retrieval_reports_same_scope_conflict_without_citation() -> None:
    service, store = _evidence_service([_candidate("POL-ONE"), _candidate("POL-TWO")])
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.refresh_for_case(
        actor=actor,
        case_id="CS-2048",
        correlation_id="corr-test",
        as_of=NOW,
    )

    assert result.status is EvidenceRetrievalStatus.CONFLICTING
    assert result.evidence == []
    assert store.bindings == []


def test_retrieval_bounds_candidates_without_treating_corpus_size_as_conflict() -> None:
    service, store = _evidence_service(
        [
            _candidate(f"POL-{index:03d}", scope=f"scope-{index:03d}")
            for index in range(65)
        ]
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.refresh_for_case(
        actor=actor,
        case_id="CS-2048",
        correlation_id="corr-test",
        as_of=NOW,
    )

    assert result.status is EvidenceRetrievalStatus.RELEVANT
    assert len(result.evidence) == 64
    assert len(store.bindings) == 64
    assert store.searches[0]["candidate_limit"] == 64
    assert len(cast(list[float], store.searches[0]["query_embedding"])) == 32
    assert store.searches[0]["embedding_version"] == "deterministic-hash-v1"
