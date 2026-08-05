from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.actions import (
    ActionBundleRecord,
    ActionExecutionBlocker,
    ActionRecord,
    ActionStatus,
)
from app.domain.cases import (
    BusinessObjectRecord,
    CaseCollectionWindowRecord,
    CaseRecord,
    CaseRequestRecord,
    CaseWorkspaceCollectionsRecord,
    CaseWorkspaceRecord,
    ConversationThreadRecord,
    CustomerContextRecord,
)
from app.domain.connections import (
    ConnectionEnvironment,
    ConnectionHealth,
    ConnectionRecord,
    CredentialStatus,
)
from app.domain.decision_briefs import (
    AnalysisCheckpointRecord,
    AnalysisRunRecord,
    AnalysisStatus,
    CaseProposalRecord,
    CaseProposalVersionRecord,
    CheckpointStatus,
    DecisionBriefRecord,
    DecisionProposalState,
    DecisionRiskCheck,
    ProposalConfidence,
    ProposedActionRecord,
    ResponseSuggestionStatus,
    RiskOutcome,
    SuggestedResponseRecord,
    VerifiedFact,
)
from app.domain.identity import MemberRole
from app.domain.policies import EvidenceRetrievalResult, EvidenceRetrievalStatus
from app.domain.reviews import (
    ReviewBundleRecord,
    ReviewFreshness,
    ReviewFreshnessRecord,
    ReviewPolicyState,
    ReviewRecord,
    ReviewReservationRecord,
    ReviewReservationStatus,
    ReviewSnapshotRecord,
    ReviewStatus,
    ReviewUncertainty,
)
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator

NOW = datetime(2026, 7, 30, 8, 0, tzinfo=UTC)


def valid_case_workspace(case_id: str = "CS-2048") -> CaseWorkspaceRecord:
    seed = next(
        item
        for item in DeterministicCaseSourceSimulator().fetch_cases()
        if item.public_id == case_id
    )
    organization_id = uuid4()
    internal_case_id = uuid4()
    return CaseWorkspaceRecord(
        case=CaseRecord(
            id=internal_case_id,
            public_id=seed.public_id,
            organization_id=organization_id,
            legacy_task_id=None,
            source_id=seed.source_id,
            external_reference=seed.external_reference,
            category=seed.category,
            issue=seed.issue,
            status=seed.status,
            owner_id=None,
            urgency=seed.urgency,
            risk=seed.risk,
            due_at=seed.due_at,
            impact_amount=seed.impact_amount,
            impact_currency=seed.impact_currency,
            source_freshness=seed.source_freshness,
            source_checked_at=seed.source_checked_at,
            version=1,
            created_at=seed.request.received_at,
            updated_at=seed.request.received_at,
        ),
        request=CaseRequestRecord(
            id=uuid4(),
            public_id=f"REQ-{seed.public_id}",
            organization_id=organization_id,
            case_id=internal_case_id,
            channel=seed.request.channel,
            customer_message=seed.request.customer_message,
            summary=seed.request.summary,
            received_at=seed.request.received_at,
        ),
        customer=CustomerContextRecord(
            id=uuid4(),
            organization_id=organization_id,
            case_id=internal_case_id,
            customer_id=seed.customer.customer_id,
            name=seed.customer.name,
            tier=seed.customer.tier,
            locale=seed.customer.locale,
            contact=seed.customer.contact,
            captured_at=seed.request.received_at,
        ),
        business_contexts=[
            BusinessObjectRecord(
                id=uuid4(),
                public_id=context.public_id,
                organization_id=organization_id,
                case_id=internal_case_id,
                type=context.type,
                label=context.label,
                source=context.source,
                source_reference=context.source_reference,
                status=context.status,
                fields=context.fields,
                captured_at=context.captured_at,
                source_freshness=context.freshness,
                source_checked_at=context.checked_at,
                version=1,
            )
            for context in seed.business_contexts
        ],
        owner=None,
        thread=ConversationThreadRecord(
            id=uuid4(),
            public_id=f"CV-{seed.public_id}",
            organization_id=organization_id,
            case_id=internal_case_id,
            version=1,
            updated_at=seed.request.received_at,
        ),
        messages=[],
        draft=None,
        activity=[],
        collections=CaseWorkspaceCollectionsRecord(
            business_contexts=CaseCollectionWindowRecord(
                returned=len(seed.business_contexts),
                total=len(seed.business_contexts),
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


def valid_evidence_result(
    status: EvidenceRetrievalStatus = EvidenceRetrievalStatus.RELEVANT,
) -> EvidenceRetrievalResult:
    return EvidenceRetrievalResult(
        status=status,
        reason=f"Validated evidence status: {status.value}.",
        evidence=[],
    )


def valid_decision_brief(
    *,
    policy_status: EvidenceRetrievalStatus = EvidenceRetrievalStatus.RELEVANT,
    analysis_status: AnalysisStatus = AnalysisStatus.COMPLETED,
    state: DecisionProposalState = DecisionProposalState.READY_FOR_REVIEW,
    response_status: ResponseSuggestionStatus = ResponseSuggestionStatus.READY,
    review_required: bool = True,
    impact_amount: Decimal | None = Decimal("75.00"),
    impact_currency: str | None = "USD",
    risk_outcome: RiskOutcome = RiskOutcome.REQUIRES_REVIEW,
    risk_label: str = "Financial approval",
    action_type: str = "issue_credit",
    input_fingerprint: str = "i" * 64,
    context_fingerprint: str = "c" * 64,
    evidence_fingerprint: str = "e" * 64,
    risk_fingerprint: str = "r" * 64,
    model_version: str = "deterministic:test",
    evidence_ids: list[str] | None = None,
    context_snapshot_ids: list[str] | None = None,
) -> DecisionBriefRecord:
    organization_id = uuid4()
    case_id = uuid4()
    run_id = uuid4()
    proposal_id = uuid4()
    version_id = uuid4()
    return DecisionBriefRecord(
        run=AnalysisRunRecord(
            id=run_id,
            public_id="RUN-TEST-0001",
            organization_id=organization_id,
            case_id=case_id,
            status=analysis_status,
            policy_status=policy_status,
            case_version=1,
            input_fingerprint=input_fingerprint,
            context_fingerprint=context_fingerprint,
            evidence_fingerprint=evidence_fingerprint,
            initiated_by="USR-0001",
            model_version=model_version,
            prompt_version="prompt:test",
            graph_version="graph:test",
            risk_rule_version="risk:test",
            started_at=NOW,
            completed_at=NOW,
        ),
        proposal=CaseProposalRecord(
            id=proposal_id,
            public_id="PRP-TEST-0001",
            organization_id=organization_id,
            case_id=case_id,
            current_version=1,
            state=state,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        ),
        version=CaseProposalVersionRecord(
            id=version_id,
            public_id="PRV-TEST-0001",
            organization_id=organization_id,
            case_id=case_id,
            proposal_id=proposal_id,
            analysis_run_id=run_id,
            legacy_proposal_version_id=None,
            version=1,
            immutable=True,
            outcome="Issue a controlled account credit.",
            impact_amount=impact_amount,
            impact_currency=impact_currency if impact_amount is not None else None,
            confidence=ProposalConfidence.MEDIUM,
            uncertainty="The source records are current and internally consistent.",
            rationale="The verified charge is covered by the current billing policy.",
            state=state,
            facts=[
                VerifiedFact(
                    id="FACT-TEST-0001",
                    statement="The duplicate charge is present on the invoice.",
                    source="invoice:INV-2048",
                    verified_at=NOW,
                )
            ],
            missing_information=[],
            risks=[
                DecisionRiskCheck(
                    id="RISK-TEST-0001",
                    label=risk_label,
                    outcome=risk_outcome,
                    explanation="A supervisor must approve the credit.",
                )
            ],
            evidence_ids=(
                ["EVD-TEST-0001"] if evidence_ids is None else evidence_ids
            ),
            context_snapshot_ids=(
                ["CTX-TEST-0001"]
                if context_snapshot_ids is None
                else context_snapshot_ids
            ),
            evidence_fingerprint=evidence_fingerprint,
            context_fingerprint=context_fingerprint,
            risk_fingerprint=risk_fingerprint,
            risk_rule_version="risk:test",
            model_version=model_version,
            prompt_version="prompt:test",
            graph_version="graph:test",
            created_at=NOW,
        ),
        proposed_actions=[
            ProposedActionRecord(
                id=uuid4(),
                public_id="PACT-TEST-0001",
                organization_id=organization_id,
                case_id=case_id,
                proposal_version_id=version_id,
                type=action_type,
                label="Issue account credit",
                parameters={"account_id": "ACC-2048"},
                impact_amount=impact_amount,
                impact_currency=impact_currency if impact_amount is not None else None,
                expected_outcome="A USD 75.00 credit is recorded once.",
                review_required=review_required,
                created_at=NOW,
            )
        ],
        response_draft=SuggestedResponseRecord(
            id=uuid4(),
            public_id="RSP-TEST-0001",
            organization_id=organization_id,
            case_id=case_id,
            proposal_version_id=version_id,
            subject="Update on your billing case",
            body="We verified the duplicate charge and prepared a credit for approval.",
            status=response_status,
            version=1,
            created_at=NOW,
        ),
        checkpoints=[
            AnalysisCheckpointRecord(
                id=uuid4(),
                public_id="CHK-TEST-0001",
                organization_id=organization_id,
                case_id=case_id,
                analysis_run_id=run_id,
                sequence=1,
                step="decision",
                status=CheckpointStatus.COMPLETED,
                summary="Decision controls completed.",
                input_fingerprint="i" * 64,
                output_fingerprint="o" * 64,
                created_at=NOW,
            )
        ],
    )


def valid_review_bundle(
    *,
    status: ReviewStatus = ReviewStatus.PENDING,
    required_role: MemberRole = MemberRole.SUPERVISOR,
    execution_eligible: bool = True,
    include_reservation: bool = False,
) -> ReviewBundleRecord:
    organization_id = uuid4()
    case_id = uuid4()
    proposal_id = uuid4()
    proposal_version_id = uuid4()
    review_id = uuid4()
    snapshot_id = uuid4()
    snapshot_fingerprint = "s" * 64
    reservation = (
        ReviewReservationRecord(
            id=uuid4(),
            public_id="RSV-TEST-0001",
            organization_id=organization_id,
            case_id=case_id,
            review_id=review_id,
            reviewer_id=uuid4(),
            reviewer_public_id="USR-0002",
            reviewer_name="Rina Supervisor",
            reviewer_role=MemberRole.SUPERVISOR,
            snapshot_fingerprint=snapshot_fingerprint,
            status=ReviewReservationStatus.ACTIVE,
            reserved_at=NOW,
            expires_at=NOW + timedelta(minutes=15),
            consumed_at=None,
        )
        if include_reservation
        else None
    )
    return ReviewBundleRecord(
        review=ReviewRecord(
            id=review_id,
            public_id="RV-TEST-0001",
            organization_id=organization_id,
            case_id=case_id,
            proposal_id=proposal_id,
            proposal_version_id=proposal_version_id,
            status=status,
            review_reason="Financial impact requires supervisor approval.",
            policy_state=ReviewPolicyState.SUPPORTED,
            uncertainty=ReviewUncertainty.MEDIUM,
            impact_amount=Decimal("75.00"),
            impact_currency="USD",
            submitted_by_id=uuid4(),
            submitted_by_public_id="USR-0001",
            submitted_by_name="Maya Specialist",
            submitted_by_role=MemberRole.SPECIALIST,
            submitted_at=NOW,
            version=1,
            updated_at=NOW,
        ),
        snapshot=ReviewSnapshotRecord(
            id=snapshot_id,
            public_id="RVS-TEST-0001",
            organization_id=organization_id,
            case_id=case_id,
            review_id=review_id,
            proposal_id=proposal_id,
            proposal_version_id=proposal_version_id,
            case_version=1,
            proposal_version=1,
            proposal_fingerprint="p" * 64,
            context_fingerprint="c" * 64,
            evidence_fingerprint="e" * 64,
            risk_fingerprint="r" * 64,
            risk_rule_version="risk:test",
            snapshot_fingerprint=snapshot_fingerprint,
            approval_rule_id="APR-TEST-0001",
            approval_rule_name="Supervisor financial review",
            approval_rule_explanation="Supervisor approval is required for this amount.",
            required_role=required_role,
            approval_rule_version=1,
            execution_eligible=execution_eligible,
            created_at=NOW,
        ),
        case_public_id="CS-2048",
        proposal_public_id="PRP-TEST-0001",
        reservation=reservation,
        decisions=[],
    )


def valid_review_freshness() -> ReviewFreshnessRecord:
    return ReviewFreshnessRecord(
        status=ReviewFreshness.CURRENT,
        checked_at=NOW,
        reason=None,
    )


def valid_action_bundle(
    *,
    status: ActionStatus = ActionStatus.READY,
    execution_blocker: ActionExecutionBlocker | None = None,
    adapter_key: str = "deterministic_demo",
) -> ActionBundleRecord:
    organization_id = uuid4()
    case_id = uuid4()
    action_id = uuid4()
    proposal_id = uuid4()
    proposal_version_id = uuid4()
    review_id = uuid4()
    connection_id = uuid4()
    now = NOW
    return ActionBundleRecord(
        action=ActionRecord(
            id=action_id,
            public_id="ACT-TEST-0001",
            organization_id=organization_id,
            case_id=case_id,
            proposal_id=proposal_id,
            proposal_version_id=proposal_version_id,
            proposed_action_id=uuid4(),
            review_id=review_id,
            review_snapshot_id=uuid4(),
            review_decision_id=uuid4(),
            connection_id=connection_id,
            legacy_proposal_version_id=None,
            type="issue_credit",
            label="Issue account credit",
            target="ACC-2048",
            typed_parameters={"account_id": "ACC-2048"},
            impact_amount=Decimal("75.00"),
            impact_currency="USD",
            expected_outcome="A USD 75.00 credit is recorded once.",
            observed_outcome=None,
            status=status,
            execution_blocker=execution_blocker,
            execution_eligible=True,
            idempotency_key="idem-test-action-0001",
            authorization_expires_at=now + timedelta(hours=1),
            owner_id=None,
            owner_public_id=None,
            owner_name=None,
            attempt_count=0,
            version=1,
            created_at=now,
            updated_at=now,
        ),
        case_public_id="CS-2048",
        proposal_public_id="PRP-TEST-0001",
        proposal_version=1,
        review_public_id="RV-TEST-0001",
        review_snapshot_fingerprint="s" * 64,
        approved_at=now,
        approved_by_public_id="USR-0002",
        approved_by_name="Rina Supervisor",
        approved_by_role=MemberRole.SUPERVISOR,
        approval_rule="Supervisor financial review",
        connection=ConnectionRecord(
            id=connection_id,
            public_id="CON-TEST-0001",
            organization_id=organization_id,
            name="Controlled billing sandbox",
            provider_type="deterministic_demo",
            adapter_key=adapter_key,
            environment=ConnectionEnvironment.DEMO,
            health=ConnectionHealth.HEALTHY,
            last_checked_at=now,
            credential_status=CredentialStatus.DEMO,
            read_capabilities=["account.read"],
            write_capabilities=["credit.write"],
            action_types=["issue_credit"],
            affected_work=[],
            version=1,
            created_at=now,
            updated_at=now,
        ),
        attempts=[],
        receipt=None,
        reconciliations=[],
    )
