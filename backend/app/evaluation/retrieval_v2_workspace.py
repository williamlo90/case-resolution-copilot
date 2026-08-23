from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.cases import (
    BusinessObjectRecord,
    BusinessObjectType,
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
    SourceFreshness,
)
from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    ActorOrganizationContext,
    AuthenticationMode,
    MemberRole,
)
from app.evaluation.retrieval_v2_contract import RetrievalBenchmarkCase


def benchmark_actor(organization_public_id: str) -> ActorContext:
    return ActorContext(
        actor_id="USR-BENCHMARK",
        organization_id=organization_public_id,
        name="Retrieval Benchmark",
        kind=ActorKind.MEMBER,
        role=MemberRole.ADMINISTRATOR,
        permissions=ROLE_PERMISSIONS[MemberRole.ADMINISTRATOR],
        authentication_mode=AuthenticationMode.DETERMINISTIC_DEVELOPMENT,
        organization=ActorOrganizationContext(
            id=organization_public_id,
            name="Synthetic benchmark workspace",
            slug=organization_public_id.lower(),
            version=1,
            locale="en-US",
            time_zone="UTC",
        ),
    )


def benchmark_workspace(case: RetrievalBenchmarkCase) -> CaseWorkspaceRecord:
    observed_at = benchmark_as_of(case)
    organization_id = _stable_uuid(case.organization_public_id)
    case_id = _stable_uuid(case.id)
    business_contexts = [
        BusinessObjectRecord(
            id=_stable_uuid(f"{case.id}:context:{index}"),
            public_id=f"CTX-{case.id.removeprefix('RAG2-')}-{index:02d}",
            organization_id=organization_id,
            case_id=case_id,
            type=BusinessObjectType.OTHER,
            label=f"Synthetic product context {index}",
            source="retrieval-benchmark",
            source_reference=f"BENCH-{index}",
            status="current",
            fields={"product": product},
            captured_at=observed_at,
            source_freshness=SourceFreshness.CURRENT,
            source_checked_at=observed_at,
            version=1,
        )
        for index, product in enumerate(case.products, start=1)
    ]
    return CaseWorkspaceRecord(
        case=CaseRecord(
            id=case_id,
            public_id=f"CS-BENCH-{case.id.removeprefix('RAG2-')}",
            organization_id=organization_id,
            legacy_task_id=None,
            source_id=f"retrieval-benchmark:{case.id.lower()}",
            external_reference=case.id,
            category=case.category,
            issue=case.issue,
            status=CaseStatus.INVESTIGATING,
            owner_id=None,
            urgency=CaseUrgency.MEDIUM,
            risk=CaseRisk.MEDIUM,
            due_at=observed_at + timedelta(days=1),
            impact_amount=None,
            impact_currency=None,
            source_freshness=SourceFreshness.CURRENT,
            source_checked_at=observed_at,
            version=1,
            created_at=observed_at,
            updated_at=observed_at,
        ),
        request=CaseRequestRecord(
            id=_stable_uuid(f"{case.id}:request"),
            public_id=f"REQ-BENCH-{case.id.removeprefix('RAG2-')}",
            organization_id=organization_id,
            case_id=case_id,
            channel=case.channel,
            customer_message=case.request_summary,
            summary=case.request_summary,
            received_at=observed_at,
        ),
        customer=CustomerContextRecord(
            id=_stable_uuid(f"{case.id}:customer"),
            organization_id=organization_id,
            case_id=case_id,
            customer_id=f"CUS-BENCH-{case.id.removeprefix('RAG2-')}",
            name="Synthetic Customer",
            tier=case.customer_tier,
            locale=f"en-{case.region.upper()}",
            contact="benchmark@example.invalid",
            captured_at=observed_at,
        ),
        business_contexts=business_contexts,
        owner=None,
        thread=ConversationThreadRecord(
            id=_stable_uuid(f"{case.id}:thread"),
            public_id=f"CV-BENCH-{case.id.removeprefix('RAG2-')}",
            organization_id=organization_id,
            case_id=case_id,
            version=1,
            updated_at=observed_at,
        ),
        messages=[],
        draft=None,
        activity=[],
        collections=CaseWorkspaceCollectionsRecord(
            business_contexts=CaseCollectionWindowRecord(
                returned=len(business_contexts),
                total=len(business_contexts),
                has_more=False,
            ),
            messages=CaseCollectionWindowRecord(returned=0, total=0, has_more=False),
            activity=CaseCollectionWindowRecord(returned=0, total=0, has_more=False),
        ),
    )


def benchmark_as_of(case: RetrievalBenchmarkCase) -> datetime:
    return datetime.strptime(case.as_of, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _stable_uuid(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"case-resolution-copilot:{value}")
