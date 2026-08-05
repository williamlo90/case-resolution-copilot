from datetime import UTC, datetime
from hashlib import sha256

from app.api.presenters.decision_briefs import present_decision_brief
from app.api.schemas.cases import (
    BusinessObjectSnapshotResponse,
    CaseActivityResponse,
    CaseCollectionWindowResponse,
    CaseCustomerSummaryResponse,
    CaseOwnerResponse,
    CaseQueueSummaryResponse,
    CaseRequestResponse,
    CaseSummaryResponse,
    CaseWorkspaceCollectionsResponse,
    CaseWorkspaceResponse,
    CustomerContextResponse,
)
from app.api.schemas.common import MoneyResponse, SourceFreshnessResponse
from app.api.schemas.conversations import (
    ConversationMessageResponse,
    ConversationThreadResponse,
)
from app.api.schemas.policies import PolicyEvidenceResponse
from app.api.schemas.proposals import ResponseDraftResponse
from app.domain.cases import (
    CaseActivityRecord,
    CaseCollectionWindowRecord,
    CaseListItemRecord,
    CaseQueueSummaryRecord,
    CaseWorkspaceRecord,
    ConversationMessageRecord,
)
from app.domain.policies import PolicyEvidenceBundle
from app.services.case_history_service import (
    CaseHistoryKind,
    encode_case_history_cursor,
)
from app.services.case_workspace_query import CaseWorkspaceProjection


def present_case_queue_summary(
    record: CaseQueueSummaryRecord,
) -> CaseQueueSummaryResponse:
    return CaseQueueSummaryResponse(
        total=record.total,
        attention=record.attention,
        review=record.review,
        sla_at_risk=record.sla_at_risk,
        unassigned=record.unassigned,
    )


def _activity_label(event_type: str) -> str:
    labels = {
        "case.decision_brief_generated": "Decision brief prepared",
    }
    return labels.get(
        event_type,
        event_type.replace(".", " ").replace("_", " ").title(),
    )


def present_case_summary(
    record: CaseListItemRecord | CaseWorkspaceRecord,
    *,
    organization_id: str,
) -> CaseSummaryResponse:
    case = record.case
    customer = record.customer
    remaining_seconds = max(0, int((case.due_at - datetime.now(UTC)).total_seconds()))
    impact = (
        MoneyResponse(amount=case.impact_amount, currency=case.impact_currency)
        if case.impact_amount is not None and case.impact_currency is not None
        else None
    )
    owner = None
    if record.owner is not None:
        initials = "".join(part[0] for part in record.owner.name.split() if part)[:3].upper()
        owner = CaseOwnerResponse(
            id=record.owner.public_id,
            name=record.owner.name,
            initials=initials or "?",
        )
    return CaseSummaryResponse(
        id=case.public_id,
        organization_id=organization_id,
        source_id=case.source_id,
        external_reference=case.external_reference,
        category=case.category,
        issue=case.issue,
        customer=CaseCustomerSummaryResponse(
            name=customer.name,
            is_vip=customer.tier.value in {"vip", "enterprise"},
        ),
        status=case.status,
        owner=owner,
        urgency=case.urgency,
        risk=case.risk,
        sla_minutes_remaining=remaining_seconds // 60,
        updated_at=case.updated_at,
        source_freshness=SourceFreshnessResponse(
            status=case.source_freshness.value,
            checked_at=case.source_checked_at,
        ),
        impact=impact,
        version=case.version,
    )


def present_conversation(
    workspace: CaseWorkspaceRecord,
    *,
    organization_id: str,
) -> ConversationThreadResponse:
    return ConversationThreadResponse(
        id=workspace.thread.public_id,
        organization_id=organization_id,
        case_id=workspace.case.public_id,
        messages=[
            present_conversation_message(
                message,
                organization_id=organization_id,
                case_id=workspace.case.public_id,
            )
            for message in workspace.messages
        ],
        version=workspace.thread.version,
        updated_at=workspace.thread.updated_at,
    )


def present_conversation_message(
    message: ConversationMessageRecord,
    *,
    organization_id: str,
    case_id: str,
) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        id=message.public_id,
        organization_id=organization_id,
        case_id=case_id,
        author_type=message.author_type,
        author_id=message.author_id,
        author_name=message.author_name,
        channel=message.channel.value,
        body=message.body,
        internal=message.internal,
        source_reference=message.source_reference,
        created_at=message.created_at,
        version=message.version,
    )


def present_case_activity(activity: CaseActivityRecord) -> CaseActivityResponse:
    return CaseActivityResponse(
        id=f"AUD-{sha256(activity.id.bytes).hexdigest()[:16].upper()}",
        label=_activity_label(activity.event_type),
        detail=activity.summary,
        actor=activity.actor_id or "System",
        timestamp=activity.occurred_at,
        status="completed",
    )


def present_collection_window(
    window: CaseCollectionWindowRecord,
    *,
    kind: CaseHistoryKind | None,
    case_id: str,
) -> CaseCollectionWindowResponse:
    return CaseCollectionWindowResponse(
        returned=window.returned,
        total=window.total,
        has_more=window.has_more,
        next_cursor=(
            encode_case_history_cursor(
                window.next_position,
                kind=kind,
                case_id=case_id,
            )
            if kind is not None
            else None
        ),
    )


def present_policy_evidence(bundle: PolicyEvidenceBundle) -> PolicyEvidenceResponse:
    evidence = bundle.evidence
    effective_date = (
        evidence.effective_from.date().isoformat()
        if evidence.effective_from is not None
        else "Immediately effective"
    )
    return PolicyEvidenceResponse(
        id=evidence.public_id,
        policy_id=bundle.policy.public_id,
        policy_version_id=bundle.version.public_id,
        policy_version=bundle.version.version,
        clause_id=bundle.clause.public_id,
        title=bundle.policy.title,
        citation=evidence.citation,
        excerpt=evidence.excerpt,
        applicability=evidence.applicability,
        effective_date=effective_date,
        freshness=evidence.freshness,
        conflict_state=evidence.conflict_state,
        fingerprint=evidence.fingerprint,
    )


def present_case_workspace(
    projection: CaseWorkspaceProjection,
    *,
    organization_id: str,
) -> CaseWorkspaceResponse:
    workspace = projection.workspace
    draft = workspace.draft
    decision = (
        present_decision_brief(
            projection.brief,
            organization_id=organization_id,
            case_id=workspace.case.public_id,
        )
        if projection.brief is not None
        else None
    )
    return CaseWorkspaceResponse(
        case=present_case_summary(workspace, organization_id=organization_id),
        request=CaseRequestResponse(
            id=workspace.request.public_id,
            received_at=workspace.request.received_at,
            channel=workspace.request.channel.value,
            customer_message=workspace.request.customer_message,
            summary=workspace.request.summary,
        ),
        conversation=present_conversation(
            workspace,
            organization_id=organization_id,
        ),
        customer=CustomerContextResponse(
            id=workspace.customer.customer_id,
            tier=workspace.customer.tier.value,
            locale=workspace.customer.locale,
            contact=workspace.customer.contact,
        ),
        business_contexts=[
            BusinessObjectSnapshotResponse(
                id=context.public_id,
                organization_id=organization_id,
                case_id=workspace.case.public_id,
                type=context.type.value,
                label=context.label,
                source=context.source,
                source_reference=context.source_reference,
                status=context.status,
                fields={key: str(value) for key, value in context.fields.items()},
                captured_at=context.captured_at,
                source_freshness=SourceFreshnessResponse(
                    status=context.source_freshness.value,
                    checked_at=context.source_checked_at,
                ),
                version=context.version,
            )
            for context in workspace.business_contexts
        ],
        facts=decision.facts if decision is not None else [],
        missing_information=(decision.missing_information if decision is not None else []),
        evidence=[present_policy_evidence(item) for item in projection.evidence],
        risks=decision.risks if decision is not None else [],
        proposal=decision.proposal if decision is not None else None,
        response_draft=(
            ResponseDraftResponse(
                id=draft.public_id,
                version=draft.version,
                subject=draft.subject,
                body=draft.body,
                status=draft.status,
                updated_at=draft.updated_at,
            )
            if draft is not None
            else (decision.response_draft if decision is not None else None)
        ),
        proposed_actions=decision.proposed_actions if decision is not None else [],
        activity=[present_case_activity(activity) for activity in workspace.activity],
        collections=CaseWorkspaceCollectionsResponse(
            business_contexts=present_collection_window(
                workspace.collections.business_contexts,
                kind=None,
                case_id=workspace.case.public_id,
            ),
            messages=present_collection_window(
                workspace.collections.messages,
                kind="conversation",
                case_id=workspace.case.public_id,
            ),
            activity=present_collection_window(
                workspace.collections.activity,
                kind="activity",
                case_id=workspace.case.public_id,
            ),
        ),
        available_commands=list(projection.available_commands),
    )
