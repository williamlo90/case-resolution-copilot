from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.cases import CaseConcurrencyConflict
from app.domain.decision_briefs import (
    DecisionBriefCreate,
    DecisionBriefRecord,
    ProposalConcurrencyConflict,
    ProposalNotFound,
    ProposalSnapshotMismatch,
)
from app.persistence.decision_brief_helpers import (
    decision_brief_audit_details as _decision_brief_audit_details,
)
from app.persistence.decision_brief_helpers import hash_value as _hash
from app.persistence.decision_brief_helpers import stable_public_id as _stable_public_id
from app.persistence.decision_brief_queries import DecisionBriefQueryRepository
from app.persistence.models import (
    AuditEventModel,
    BusinessObjectSnapshotModel,
    CaseAnalysisCheckpointModel,
    CaseAnalysisRunModel,
    CaseModel,
    CasePolicyEvidenceModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseProposedActionModel,
    ProposalContextBindingModel,
    ProposalEvidenceBindingModel,
    ProposalResponseDraftModel,
    utc_now,
)


class DecisionBriefWriter:
    def __init__(
        self,
        session: Session,
        queries: DecisionBriefQueryRepository,
    ) -> None:
        self._session = session
        self._queries = queries

    def create_or_get(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        command: DecisionBriefCreate,
        correlation_id: str,
    ) -> DecisionBriefRecord:
        scoped = self._queries.scoped_case(
            organization_public_id,
            case_public_id,
        )
        if scoped is None:
            raise ProposalNotFound("The case was not found.")
        _, case = scoped
        if case.version != command.expected_case_version:
            raise CaseConcurrencyConflict(
                expected_version=command.expected_case_version,
                current_version=case.version,
            )
        existing = self._queries.load_by_input_fingerprint(
            case=case,
            input_fingerprint=command.input_fingerprint,
        )
        if existing is not None:
            return existing

        now = utc_now()
        run = CaseAnalysisRunModel(
            public_id=_stable_public_id(
                "ANL",
                case.public_id,
                command.input_fingerprint,
            ),
            organization_id=case.organization_id,
            case_id=case.id,
            status=command.analysis.status.value,
            policy_status=command.analysis.policy_status.value,
            case_version=command.expected_case_version,
            input_fingerprint=command.input_fingerprint,
            context_fingerprint=command.context_fingerprint,
            evidence_fingerprint=command.evidence_fingerprint,
            initiated_by=actor_id,
            model_version=command.analysis.model_version,
            prompt_version=command.analysis.prompt_version,
            graph_version=command.analysis.graph_version,
            risk_rule_version=command.analysis.risk_rule_version,
            started_at=now,
            completed_at=now,
        )
        self._session.add(run)
        self._session.flush()

        proposal = self._session.scalar(
            select(CaseProposalModel).where(
                CaseProposalModel.organization_id == case.organization_id,
                CaseProposalModel.case_id == case.id,
            )
        )
        if proposal is None:
            proposal = CaseProposalModel(
                public_id=_stable_public_id(
                    "PRP",
                    organization_public_id,
                    case.public_id,
                ),
                organization_id=case.organization_id,
                case_id=case.id,
                current_version=1,
                state=command.analysis.state.value,
                version=1,
                created_at=now,
                updated_at=now,
            )
            self._session.add(proposal)
            self._session.flush()
            proposal_version = 1
        else:
            latest_version = self._session.scalar(
                select(func.max(CaseProposalVersionModel.version)).where(
                    CaseProposalVersionModel.organization_id == case.organization_id,
                    CaseProposalVersionModel.case_id == case.id,
                    CaseProposalVersionModel.proposal_id == proposal.id,
                )
            )
            proposal_version = (latest_version or 0) + 1
            expected_root_version = proposal.version
            updated = self._session.scalar(
                update(CaseProposalModel)
                .where(
                    CaseProposalModel.id == proposal.id,
                    CaseProposalModel.organization_id == case.organization_id,
                    CaseProposalModel.version == expected_root_version,
                )
                .values(
                    current_version=proposal_version,
                    state=command.analysis.state.value,
                    version=CaseProposalModel.version + 1,
                    updated_at=now,
                )
                .returning(CaseProposalModel)
            )
            if updated is None:
                current = self._session.scalar(
                    select(CaseProposalModel.version).where(
                        CaseProposalModel.id == proposal.id,
                        CaseProposalModel.organization_id == case.organization_id,
                    )
                )
                raise ProposalConcurrencyConflict(
                    expected_version=expected_root_version,
                    current_version=current or expected_root_version,
                )
            proposal = updated

        version_id = uuid4()
        risk_fingerprint = _hash([risk.model_dump(mode="json") for risk in command.analysis.risks])
        version_model = CaseProposalVersionModel(
            id=version_id,
            public_id=_stable_public_id(
                "PRPV",
                proposal.public_id,
                str(proposal_version),
            ),
            organization_id=case.organization_id,
            case_id=case.id,
            proposal_id=proposal.id,
            analysis_run_id=run.id,
            legacy_proposal_version_id=None,
            version=proposal_version,
            immutable=True,
            outcome=command.analysis.outcome,
            impact_amount=command.analysis.impact_amount,
            impact_currency=command.analysis.impact_currency,
            confidence=command.analysis.confidence.value,
            uncertainty=command.analysis.uncertainty,
            rationale=command.analysis.rationale,
            state=command.analysis.state.value,
            facts=[fact.model_dump(mode="json") for fact in command.analysis.facts],
            missing_information=[
                gap.model_dump(mode="json") for gap in command.analysis.missing_information
            ],
            risks=[risk.model_dump(mode="json") for risk in command.analysis.risks],
            evidence_fingerprint=command.evidence_fingerprint,
            context_fingerprint=command.context_fingerprint,
            risk_fingerprint=risk_fingerprint,
            risk_rule_version=command.analysis.risk_rule_version,
            model_version=command.analysis.model_version,
            prompt_version=command.analysis.prompt_version,
            graph_version=command.analysis.graph_version,
            created_at=now,
        )
        self._session.add(version_model)
        self._session.flush()
        self._bind_evidence(case, proposal, version_model, command)
        self._bind_context(case, proposal, version_model, command)
        self._add_actions(
            case=case,
            proposal=proposal,
            version_id=version_id,
            proposal_version=proposal_version,
            command=command,
            created_at=now,
        )
        self._session.add(
            ProposalResponseDraftModel(
                public_id=_stable_public_id(
                    "DRF",
                    proposal.public_id,
                    str(proposal_version),
                ),
                organization_id=case.organization_id,
                case_id=case.id,
                proposal_id=proposal.id,
                proposal_version_id=version_id,
                subject=command.analysis.response_draft.subject,
                body=command.analysis.response_draft.body,
                status=command.analysis.response_draft.status.value,
                version=1,
                created_at=now,
            )
        )
        for checkpoint in command.analysis.checkpoints:
            self._session.add(
                CaseAnalysisCheckpointModel(
                    public_id=_stable_public_id(
                        "CHK",
                        run.public_id,
                        str(checkpoint.sequence),
                    ),
                    organization_id=case.organization_id,
                    case_id=case.id,
                    analysis_run_id=run.id,
                    sequence=checkpoint.sequence,
                    step=checkpoint.step,
                    status=checkpoint.status.value,
                    summary=checkpoint.summary,
                    input_fingerprint=checkpoint.input_fingerprint,
                    output_fingerprint=checkpoint.output_fingerprint,
                    created_at=now,
                )
            )
        audit_summary, drafting_mode = _decision_brief_audit_details(command.analysis)
        self._session.add(
            AuditEventModel(
                organization_id=case.organization_id,
                task_id=None,
                run_id=None,
                event_type="case.decision_brief_generated",
                actor_type=actor_type,
                actor_id=actor_id,
                subject_type="case",
                subject_id=case.public_id,
                summary=audit_summary,
                data={
                    "proposal_id": proposal.public_id,
                    "proposal_version": proposal_version,
                    "analysis_run_id": run.public_id,
                    "input_fingerprint": command.input_fingerprint,
                    "policy_status": command.analysis.policy_status.value,
                    "drafting_mode": drafting_mode,
                    "model_version": command.analysis.model_version,
                },
                correlation_id=correlation_id,
            )
        )
        self._session.flush()
        return self._queries.load_brief(proposal, proposal_version)

    def _bind_evidence(
        self,
        case: CaseModel,
        proposal: CaseProposalModel,
        version: CaseProposalVersionModel,
        command: DecisionBriefCreate,
    ) -> None:
        for reference in command.evidence:
            evidence = self._session.scalar(
                select(CasePolicyEvidenceModel).where(
                    CasePolicyEvidenceModel.organization_id == case.organization_id,
                    CasePolicyEvidenceModel.case_id == case.id,
                    CasePolicyEvidenceModel.public_id == reference.public_id,
                    CasePolicyEvidenceModel.fingerprint == reference.fingerprint,
                )
            )
            if evidence is None:
                raise ProposalSnapshotMismatch(
                    f"Policy evidence {reference.public_id} changed before proposal persistence."
                )
            self._session.add(
                ProposalEvidenceBindingModel(
                    organization_id=case.organization_id,
                    case_id=case.id,
                    proposal_id=proposal.id,
                    proposal_version_id=version.id,
                    evidence_id=evidence.id,
                    evidence_fingerprint=evidence.fingerprint,
                )
            )

    def _bind_context(
        self,
        case: CaseModel,
        proposal: CaseProposalModel,
        version: CaseProposalVersionModel,
        command: DecisionBriefCreate,
    ) -> None:
        for reference in command.contexts:
            context = self._session.scalar(
                select(BusinessObjectSnapshotModel).where(
                    BusinessObjectSnapshotModel.organization_id == case.organization_id,
                    BusinessObjectSnapshotModel.case_id == case.id,
                    BusinessObjectSnapshotModel.public_id == reference.public_id,
                    BusinessObjectSnapshotModel.version == reference.version,
                )
            )
            if context is None:
                raise ProposalSnapshotMismatch(
                    f"Business context {reference.public_id} changed before proposal persistence."
                )
            self._session.add(
                ProposalContextBindingModel(
                    organization_id=case.organization_id,
                    case_id=case.id,
                    proposal_id=proposal.id,
                    proposal_version_id=version.id,
                    context_id=context.id,
                    snapshot_version=context.version,
                    context_fingerprint=reference.fingerprint,
                )
            )

    def _add_actions(
        self,
        *,
        case: CaseModel,
        proposal: CaseProposalModel,
        version_id: UUID,
        proposal_version: int,
        command: DecisionBriefCreate,
        created_at: datetime,
    ) -> None:
        for index, action in enumerate(
            command.analysis.proposed_actions,
            start=1,
        ):
            self._session.add(
                CaseProposedActionModel(
                    public_id=_stable_public_id(
                        "PRA",
                        proposal.public_id,
                        str(proposal_version),
                        str(index),
                    ),
                    organization_id=case.organization_id,
                    case_id=case.id,
                    proposal_id=proposal.id,
                    proposal_version_id=version_id,
                    type=action.type,
                    label=action.label,
                    parameters=action.parameters,
                    impact_amount=action.impact_amount,
                    impact_currency=action.impact_currency,
                    expected_outcome=action.expected_outcome,
                    review_required=action.review_required,
                    created_at=created_at,
                )
            )
