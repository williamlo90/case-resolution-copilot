from app.api.schemas.cases import (
    MissingInformationResponse,
    RiskCheckResponse,
    VerifiedFactResponse,
)
from app.api.schemas.common import MoneyResponse
from app.api.schemas.decision_briefs import (
    AnalysisCheckpointResponse,
    AnalysisRunResponse,
    DecisionBriefResponse,
)
from app.api.schemas.proposals import (
    ProposalResponse,
    ProposedActionResponse,
    ResponseDraftResponse,
)
from app.domain.decision_briefs import DecisionBriefRecord


def present_decision_brief(
    brief: DecisionBriefRecord,
    *,
    organization_id: str,
    case_id: str,
) -> DecisionBriefResponse:
    version = brief.version
    return DecisionBriefResponse(
        analysis=AnalysisRunResponse(
            id=brief.run.public_id,
            case_id=case_id,
            status=brief.run.status,
            policy_status=brief.run.policy_status,
            case_version=brief.run.case_version,
            initiated_by=brief.run.initiated_by,
            model_version=brief.run.model_version,
            prompt_version=brief.run.prompt_version,
            graph_version=brief.run.graph_version,
            risk_rule_version=brief.run.risk_rule_version,
            completed_at=brief.run.completed_at,
        ),
        facts=[
            VerifiedFactResponse(
                id=fact.id,
                statement=fact.statement,
                source=fact.source,
                verified_at=fact.verified_at,
            )
            for fact in version.facts
        ],
        missing_information=[
            MissingInformationResponse(
                id=gap.id,
                label=gap.label,
                description=gap.description,
                blocking=gap.blocking,
            )
            for gap in version.missing_information
        ],
        risks=[
            RiskCheckResponse(
                id=risk.id,
                label=risk.label,
                outcome=risk.outcome.value,
                explanation=risk.explanation,
            )
            for risk in version.risks
        ],
        proposal=ProposalResponse(
            id=brief.proposal.public_id,
            organization_id=organization_id,
            case_id=case_id,
            version=version.version,
            outcome=version.outcome,
            impact=(
                MoneyResponse(
                    amount=version.impact_amount,
                    currency=version.impact_currency,
                )
                if version.impact_amount is not None and version.impact_currency is not None
                else None
            ),
            confidence=version.confidence.value,
            uncertainty=version.uncertainty,
            rationale=version.rationale,
            state=(
                brief.proposal.state.value
                if brief.proposal.current_version == version.version
                else version.state.value
            ),
            evidence_ids=version.evidence_ids,
            context_snapshot_ids=version.context_snapshot_ids,
            risk_rule_version=version.risk_rule_version,
            model_version=version.model_version,
            prompt_version=version.prompt_version,
            graph_version=version.graph_version,
            created_at=version.created_at,
        ),
        proposed_actions=[
            ProposedActionResponse(
                id=action.public_id,
                type=action.type,
                label=action.label,
                impact=(
                    MoneyResponse(
                        amount=action.impact_amount,
                        currency=action.impact_currency,
                    )
                    if action.impact_amount is not None and action.impact_currency is not None
                    else None
                ),
                expected_outcome=action.expected_outcome,
                review_required=action.review_required,
            )
            for action in brief.proposed_actions
        ],
        response_draft=ResponseDraftResponse(
            id=brief.response_draft.public_id,
            version=brief.response_draft.version,
            source="suggested",
            edit_version=0,
            subject=brief.response_draft.subject,
            body=brief.response_draft.body,
            status=brief.response_draft.status.value,
            updated_at=brief.response_draft.created_at,
        ),
        checkpoints=[
            AnalysisCheckpointResponse(
                id=checkpoint.public_id,
                sequence=checkpoint.sequence,
                step=checkpoint.step,
                status=checkpoint.status,
                summary=checkpoint.summary,
                created_at=checkpoint.created_at,
            )
            for checkpoint in brief.checkpoints
        ],
    )
