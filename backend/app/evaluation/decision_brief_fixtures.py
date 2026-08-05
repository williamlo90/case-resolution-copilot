from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.deterministic_decision_engine import (
    DecisionEngine,
    combined_context_fingerprint,
    combined_evidence_fingerprint,
    decision_input_fingerprint,
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
from app.domain.decision_briefs import (
    AnalysisStatus,
    DecisionProposalState,
)
from app.domain.policies import (
    CasePolicyEvidenceRecord,
    EvidenceRetrievalResult,
    EvidenceRetrievalStatus,
    GovernedPolicyClauseRecord,
    GovernedPolicyVersionRecord,
    PolicyEvidenceBundle,
    PolicyLifecycleStatus,
    PolicyRecord,
    PolicyVersionStatus,
)
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator
from app.integrations.policy_source_simulator import (
    DeterministicPolicySeed,
    DeterministicPolicySourceSimulator,
)


class DecisionBriefExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^CS-\d{4}$")
    policy_status: EvidenceRetrievalStatus
    analysis_status: AnalysisStatus
    proposal_state: DecisionProposalState
    action_type: str = Field(min_length=1, max_length=100)
    provider_call_expected: bool


def decision_brief_expectations() -> tuple[DecisionBriefExpectation, ...]:
    return (
        DecisionBriefExpectation(
            case_id="CS-2048",
            policy_status=EvidenceRetrievalStatus.RELEVANT,
            analysis_status=AnalysisStatus.COMPLETED,
            proposal_state=DecisionProposalState.INFORMATION_NEEDED,
            action_type="request_information",
            provider_call_expected=True,
        ),
        DecisionBriefExpectation(
            case_id="CS-2047",
            policy_status=EvidenceRetrievalStatus.RELEVANT,
            analysis_status=AnalysisStatus.COMPLETED,
            proposal_state=DecisionProposalState.READY_FOR_REVIEW,
            action_type="issue_refund",
            provider_call_expected=True,
        ),
        DecisionBriefExpectation(
            case_id="CS-2046",
            policy_status=EvidenceRetrievalStatus.MISSING,
            analysis_status=AnalysisStatus.ABSTAINED,
            proposal_state=DecisionProposalState.INFORMATION_NEEDED,
            action_type="request_information",
            provider_call_expected=False,
        ),
    )


def build_evaluation_workspace(case_id: str) -> CaseWorkspaceRecord:
    seed = next(
        item
        for item in DeterministicCaseSourceSimulator().fetch_cases()
        if item.public_id == case_id
    )
    organization_id = uuid5(NAMESPACE_URL, f"decision-eval:org:{case_id}")
    internal_case_id = uuid5(NAMESPACE_URL, f"decision-eval:case:{case_id}")
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
            id=uuid5(NAMESPACE_URL, f"decision-eval:request:{case_id}"),
            public_id=f"REQ-{seed.public_id}",
            organization_id=organization_id,
            case_id=internal_case_id,
            channel=seed.request.channel,
            customer_message=seed.request.customer_message,
            summary=seed.request.summary,
            received_at=seed.request.received_at,
        ),
        customer=CustomerContextRecord(
            id=uuid5(NAMESPACE_URL, f"decision-eval:customer:{case_id}"),
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
                id=uuid5(NAMESPACE_URL, f"decision-eval:context:{context.public_id}"),
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
            id=uuid5(NAMESPACE_URL, f"decision-eval:thread:{case_id}"),
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


def build_evaluation_evidence(
    workspace: CaseWorkspaceRecord,
    status: EvidenceRetrievalStatus,
) -> EvidenceRetrievalResult:
    if status is not EvidenceRetrievalStatus.RELEVANT:
        return EvidenceRetrievalResult(
            status=status,
            reason=f"Evaluation policy status is {status.value}.",
            evidence=[],
        )
    seed = _policy_for(workspace)
    return EvidenceRetrievalResult(
        status=status,
        reason="A current governed policy fixture applies to this case category.",
        evidence=[_policy_bundle(workspace, seed)],
    )


def prepare_evaluation_input(
    *,
    expectation: DecisionBriefExpectation,
    engine: DecisionEngine,
) -> tuple[
    DecisionBriefExpectation,
    CaseWorkspaceRecord,
    EvidenceRetrievalResult,
    str,
]:
    workspace = build_evaluation_workspace(expectation.case_id)
    evidence = build_evaluation_evidence(workspace, expectation.policy_status)
    context_fingerprint = combined_context_fingerprint(workspace)
    evidence_fingerprint = combined_evidence_fingerprint(evidence)
    input_fingerprint = decision_input_fingerprint(
        workspace=workspace,
        evidence=evidence,
        context_fingerprint=context_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        model_version=engine.model_version,
        prompt_version=engine.prompt_version,
        graph_version=engine.graph_version,
        risk_rule_version=engine.risk_rule_version,
    )
    return expectation, workspace, evidence, input_fingerprint


def _policy_for(workspace: CaseWorkspaceRecord) -> DeterministicPolicySeed:
    category = workspace.case.category.value
    return next(
        policy
        for policy in DeterministicPolicySourceSimulator().fetch_policies()
        if category in policy.applicability.case_categories
    )


def _policy_bundle(
    workspace: CaseWorkspaceRecord,
    seed: DeterministicPolicySeed,
) -> PolicyEvidenceBundle:
    organization_id = workspace.case.organization_id
    policy_id = uuid5(NAMESPACE_URL, f"decision-eval:policy:{seed.public_id}")
    version_id = uuid5(NAMESPACE_URL, f"decision-eval:policy-version:{seed.public_id}:1")
    clause_id = uuid5(NAMESPACE_URL, f"decision-eval:clause:{seed.public_id}:1")
    content_hash = sha256(seed.source_text.encode()).hexdigest()
    clause_text = " ".join(seed.source_text.replace("#", "").split())
    clause_hash = sha256(clause_text.encode()).hexdigest()
    evidence_fingerprint = sha256(
        f"{workspace.case.public_id}:{seed.public_id}:{content_hash}".encode()
    ).hexdigest()
    return PolicyEvidenceBundle(
        policy=PolicyRecord(
            id=policy_id,
            public_id=seed.public_id,
            organization_id=organization_id,
            title=seed.title,
            description=seed.description,
            status=PolicyLifecycleStatus.PUBLISHED,
            owner_id=uuid5(NAMESPACE_URL, "decision-eval:policy-owner"),
            source_kind=seed.source_kind,
            source_name=seed.source_name,
            source_error=None,
            current_version=1,
            version=1,
            created_at=seed.effective_from,
            updated_at=seed.effective_from,
        ),
        version=GovernedPolicyVersionRecord(
            id=version_id,
            public_id=f"PV-{seed.public_id}-1",
            organization_id=organization_id,
            policy_id=policy_id,
            legacy_policy_version_id=None,
            version=1,
            record_version=1,
            status=PolicyVersionStatus.PUBLISHED,
            immutable=True,
            source_text=seed.source_text,
            content_hash=content_hash,
            decision_scope=seed.applicability.decision_scope,
            case_categories=seed.applicability.case_categories,
            products=seed.applicability.products,
            regions=seed.applicability.regions,
            channels=seed.applicability.channels,
            customer_tiers=seed.applicability.customer_tiers,
            effective_from=seed.effective_from,
            effective_to=None,
            created_by="USR-EVALUATION",
            created_at=seed.effective_from,
            submitted_at=seed.effective_from,
            published_at=seed.effective_from,
            retired_at=None,
        ),
        clause=GovernedPolicyClauseRecord(
            id=clause_id,
            public_id=f"PCL-{seed.public_id}-1",
            organization_id=organization_id,
            policy_id=policy_id,
            policy_version_id=version_id,
            sequence=1,
            heading=seed.title,
            text=clause_text,
            applies_when=workspace.case.category.value,
            content_hash=clause_hash,
            chunking_version="evaluation-v1",
            embedding_version="not-used",
            index_version="evaluation-v1",
            embedding=[],
        ),
        evidence=CasePolicyEvidenceRecord(
            id=uuid5(
                NAMESPACE_URL,
                f"decision-eval:evidence:{workspace.case.public_id}:{seed.public_id}",
            ),
            public_id=f"EVD-{workspace.case.public_id}-{seed.public_id}",
            organization_id=organization_id,
            case_id=workspace.case.id,
            policy_id=policy_id,
            policy_version_id=version_id,
            clause_id=clause_id,
            citation=f"{seed.title}, version 1",
            excerpt=clause_text,
            applicability=workspace.case.category.value,
            fingerprint=evidence_fingerprint,
            freshness="current",
            conflict_state="none",
            retrieval_score=1.0,
            policy_content_hash=content_hash,
            clause_content_hash=clause_hash,
            effective_from=seed.effective_from,
            effective_to=None,
            corpus_version="decision-evaluation-v1",
            chunking_version="evaluation-v1",
            embedding_version="not-used",
            index_version="evaluation-v1",
            recorded_at=workspace.request.received_at,
        ),
    )
