from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from app.analysis.deterministic_decision_engine import (
    DeterministicDecisionEngine,
    combined_context_fingerprint,
    combined_evidence_fingerprint,
    decision_input_fingerprint,
)
from app.domain.cases import (
    BusinessObjectRecord,
    CaseCollectionWindowRecord,
    CaseRecord,
    CaseRequestRecord,
    CaseStatus,
    CaseWorkspaceCollectionsRecord,
    CaseWorkspaceRecord,
    ConversationThreadRecord,
    CustomerContextRecord,
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
    PolicySourceKind,
)
from app.evaluation.case_resolution.models import (
    CaseResolutionBenchmarkCase,
    CaseResolutionObservation,
    GovernedPolicyFixture,
    RequiredPolicyReference,
)
from app.evaluation.public_benchmark.storage import canonical_json_bytes
from app.orchestrators.langgraph_orchestrator import LangGraphDecisionOrchestrator


def generate_deterministic_observation(
    case: CaseResolutionBenchmarkCase,
    *,
    repeat_index: int,
) -> CaseResolutionObservation:
    workspace = _workspace(case)
    evidence = _policy_evidence(case, workspace)
    engine = LangGraphDecisionOrchestrator(DeterministicDecisionEngine())
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
    started = perf_counter()
    try:
        analysis = engine.analyze(
            workspace=workspace,
            evidence=evidence,
            input_fingerprint=input_fingerprint,
        )
    except Exception as exc:
        return CaseResolutionObservation(
            case_id=case.case_id,
            repeat_index=repeat_index,
            input_sha256=_case_hash(case),
            grounded_evidence_ids=_grounded_evidence_ids(case, None),
            retrieved_policy_references=_policy_references(evidence),
            latency_ms=(perf_counter() - started) * 1000,
            analysis=None,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    return CaseResolutionObservation(
        case_id=case.case_id,
        repeat_index=repeat_index,
        input_sha256=_case_hash(case),
        grounded_evidence_ids=_grounded_evidence_ids(case, analysis),
        retrieved_policy_references=_policy_references(evidence),
        latency_ms=(perf_counter() - started) * 1000,
        analysis=analysis,
    )


def _workspace(case: CaseResolutionBenchmarkCase) -> CaseWorkspaceRecord:
    organization_id = uuid5(NAMESPACE_URL, f"crv1:org:{case.case_id}")
    internal_case_id = uuid5(NAMESPACE_URL, f"crv1:case:{case.case_id}")
    return CaseWorkspaceRecord(
        case=CaseRecord(
            id=internal_case_id,
            public_id=case.public_case_id,
            organization_id=organization_id,
            legacy_task_id=None,
            source_id="case-resolution-evaluation-v1",
            external_reference=case.external_reference,
            category=case.category,
            issue=case.request_summary,
            status=CaseStatus.INVESTIGATING,
            owner_id=None,
            urgency=case.urgency,
            risk=case.risk,
            due_at=case.as_of + timedelta(days=1),
            impact_amount=case.impact_amount,
            impact_currency=case.impact_currency,
            source_freshness=case.source_freshness,
            source_checked_at=case.source_checked_at,
            version=1,
            created_at=case.as_of,
            updated_at=case.as_of,
        ),
        request=CaseRequestRecord(
            id=uuid5(NAMESPACE_URL, f"crv1:request:{case.case_id}"),
            public_id=f"REQ-{case.public_case_id}",
            organization_id=organization_id,
            case_id=internal_case_id,
            channel=case.channel,
            customer_message=case.customer_request,
            summary=case.request_summary,
            received_at=case.as_of,
        ),
        customer=CustomerContextRecord(
            id=uuid5(NAMESPACE_URL, f"crv1:customer:{case.case_id}"),
            organization_id=organization_id,
            case_id=internal_case_id,
            customer_id=f"CUS-{case.case_id}",
            name=f"Evaluation Customer {case.case_id}",
            tier=case.customer_tier,
            locale="en-US",
            contact=f"{case.case_id.lower()}@example.invalid",
            captured_at=case.as_of,
        ),
        business_contexts=[
            BusinessObjectRecord(
                id=uuid5(NAMESPACE_URL, f"crv1:evidence:{item.public_id}"),
                public_id=item.public_id,
                organization_id=organization_id,
                case_id=internal_case_id,
                type=item.type,
                label=item.label,
                source=item.source,
                source_reference=item.source_reference,
                status=item.status,
                fields=item.fields,
                captured_at=item.captured_at,
                source_freshness=item.source_freshness,
                source_checked_at=item.source_checked_at,
                version=1,
            )
            for item in case.available_evidence
        ],
        owner=None,
        thread=ConversationThreadRecord(
            id=uuid5(NAMESPACE_URL, f"crv1:thread:{case.case_id}"),
            public_id=f"CV-{case.public_case_id}",
            organization_id=organization_id,
            case_id=internal_case_id,
            version=1,
            updated_at=case.as_of,
        ),
        messages=[],
        draft=None,
        activity=[],
        collections=CaseWorkspaceCollectionsRecord(
            business_contexts=CaseCollectionWindowRecord(
                returned=len(case.available_evidence),
                total=len(case.available_evidence),
                has_more=False,
            ),
            messages=CaseCollectionWindowRecord(returned=0, total=0, has_more=False),
            activity=CaseCollectionWindowRecord(returned=0, total=0, has_more=False),
        ),
    )


def _policy_evidence(
    case: CaseResolutionBenchmarkCase,
    workspace: CaseWorkspaceRecord,
) -> EvidenceRetrievalResult:
    policies = case.available_policy_context
    if not policies:
        return EvidenceRetrievalResult(
            status=EvidenceRetrievalStatus.MISSING,
            reason="No governed policy fixture is available.",
            evidence=[],
        )
    active = [item for item in policies if _is_active(item, case.as_of)]
    if not active:
        return EvidenceRetrievalResult(
            status=EvidenceRetrievalStatus.STALE,
            reason="No governed policy fixture is currently effective.",
            evidence=[],
        )
    scopes: dict[str, set[str]] = {}
    for item in active:
        scopes.setdefault(item.decision_scope, set()).add(item.policy_public_id)
    if any(len(policy_ids) > 1 for policy_ids in scopes.values()):
        return EvidenceRetrievalResult(
            status=EvidenceRetrievalStatus.CONFLICTING,
            reason="Multiple current governed policies claim the same decision scope.",
            evidence=[],
        )
    return EvidenceRetrievalResult(
        status=EvidenceRetrievalStatus.RELEVANT,
        reason="Current governed policy fixtures apply to this case.",
        evidence=[
            _bundle(workspace, item, sequence=index) for index, item in enumerate(active, start=1)
        ],
    )


def _is_active(policy: GovernedPolicyFixture, as_of: datetime) -> bool:
    current = as_of
    return (
        policy.version_status.value == "published"
        and (policy.effective_from is None or policy.effective_from <= current)
        and (policy.effective_to is None or current < policy.effective_to)
    )


def _bundle(
    workspace: CaseWorkspaceRecord,
    fixture: GovernedPolicyFixture,
    *,
    sequence: int,
) -> PolicyEvidenceBundle:
    org = workspace.case.organization_id
    policy_id = uuid5(NAMESPACE_URL, f"crv1:policy:{fixture.policy_public_id}")
    version_id = uuid5(
        NAMESPACE_URL, f"crv1:policy-version:{fixture.policy_public_id}:{fixture.version}"
    )
    clause_id = uuid5(NAMESPACE_URL, f"crv1:clause:{fixture.clause_public_id}")
    policy_hash = sha256(f"{fixture.policy_public_id}:{fixture.version}".encode()).hexdigest()
    clause_hash = sha256(fixture.text.encode()).hexdigest()
    fingerprint = sha256(
        f"{workspace.case.public_id}:{fixture.clause_public_id}:{clause_hash}".encode()
    ).hexdigest()
    effective_from = fixture.effective_from or workspace.case.created_at.astimezone(UTC)
    return PolicyEvidenceBundle(
        policy=PolicyRecord(
            id=policy_id,
            public_id=fixture.policy_public_id,
            organization_id=org,
            title=fixture.heading,
            description=fixture.text,
            status=PolicyLifecycleStatus.PUBLISHED,
            owner_id=uuid5(NAMESPACE_URL, "crv1:policy-owner"),
            source_kind=PolicySourceKind.MANUAL,
            source_name="Case Resolution Evaluation V1",
            source_error=None,
            current_version=fixture.version,
            version=1,
            created_at=effective_from,
            updated_at=effective_from,
        ),
        version=GovernedPolicyVersionRecord(
            id=version_id,
            public_id=f"PV-{fixture.policy_public_id}-{fixture.version}",
            organization_id=org,
            policy_id=policy_id,
            legacy_policy_version_id=None,
            version=fixture.version,
            record_version=1,
            status=fixture.version_status,
            immutable=True,
            source_text=fixture.text,
            content_hash=policy_hash,
            decision_scope=fixture.decision_scope,
            case_categories=list(fixture.case_categories),
            products=list(fixture.products),
            regions=list(fixture.regions),
            channels=list(fixture.channels),
            customer_tiers=list(fixture.customer_tiers),
            effective_from=fixture.effective_from,
            effective_to=fixture.effective_to,
            created_by="USR-EVALUATION",
            created_at=effective_from,
            submitted_at=effective_from,
            published_at=effective_from,
            retired_at=None,
        ),
        clause=GovernedPolicyClauseRecord(
            id=clause_id,
            public_id=fixture.clause_public_id,
            organization_id=org,
            policy_id=policy_id,
            policy_version_id=version_id,
            sequence=sequence,
            heading=fixture.heading,
            text=fixture.text,
            applies_when=fixture.applies_when,
            content_hash=clause_hash,
            chunking_version="crv1",
            embedding_version="not-used",
            index_version="crv1",
            embedding=[],
        ),
        evidence=CasePolicyEvidenceRecord(
            id=uuid5(
                NAMESPACE_URL,
                f"crv1:policy-evidence:{workspace.case.public_id}:{fixture.clause_public_id}",
            ),
            public_id=f"PEV-{workspace.case.public_id}-{sequence}",
            organization_id=org,
            case_id=workspace.case.id,
            policy_id=policy_id,
            policy_version_id=version_id,
            clause_id=clause_id,
            citation=f"{fixture.policy_public_id} v{fixture.version}: {fixture.heading}",
            excerpt=fixture.text,
            applicability=fixture.applies_when,
            fingerprint=fingerprint,
            freshness="current",
            conflict_state="none",
            retrieval_score=1.0,
            policy_content_hash=policy_hash,
            clause_content_hash=clause_hash,
            effective_from=fixture.effective_from,
            effective_to=fixture.effective_to,
            corpus_version="case-resolution-v1",
            chunking_version="crv1",
            embedding_version="not-used",
            index_version="crv1",
            recorded_at=workspace.request.received_at,
        ),
    )


def _policy_references(
    evidence: EvidenceRetrievalResult,
) -> tuple[RequiredPolicyReference, ...]:
    return tuple(
        RequiredPolicyReference(
            policy_public_id=item.policy.public_id,
            version=item.version.version,
            clause_public_id=item.clause.public_id,
        )
        for item in evidence.evidence
    )


def _case_hash(case: CaseResolutionBenchmarkCase) -> str:
    return sha256(canonical_json_bytes(case.model_dump(mode="json"))).hexdigest()


def _grounded_evidence_ids(
    case: CaseResolutionBenchmarkCase,
    analysis: object,
) -> tuple[str, ...]:
    facts = getattr(analysis, "facts", ())
    sources = " ".join(str(getattr(fact, "source", "")) for fact in facts).lower()
    return tuple(
        item.public_id
        for item in case.available_evidence
        if item.source_reference.lower() in sources
    )
