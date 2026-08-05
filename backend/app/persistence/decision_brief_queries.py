from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.domain.decision_briefs import (
    AnalysisCheckpointRecord,
    AnalysisRunRecord,
    CaseProposalRecord,
    CaseProposalVersionRecord,
    DecisionBriefRecord,
    ProposalSnapshotMismatch,
    ProposedActionRecord,
    SuggestedResponseRecord,
)
from app.persistence.models import (
    BusinessObjectSnapshotModel,
    CaseAnalysisCheckpointModel,
    CaseAnalysisRunModel,
    CaseModel,
    CasePolicyEvidenceModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseProposedActionModel,
    OrganizationModel,
    ProposalContextBindingModel,
    ProposalEvidenceBindingModel,
    ProposalResponseDraftModel,
)


class DecisionBriefQueryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> DecisionBriefRecord | None:
        row = self._session.execute(
            select(
                CaseProposalModel,
                CaseProposalVersionModel,
                CaseAnalysisRunModel,
                ProposalResponseDraftModel,
            )
            .join(
                CaseModel,
                and_(
                    CaseModel.organization_id == CaseProposalModel.organization_id,
                    CaseModel.id == CaseProposalModel.case_id,
                ),
            )
            .join(
                OrganizationModel,
                OrganizationModel.id == CaseModel.organization_id,
            )
            .outerjoin(
                CaseProposalVersionModel,
                and_(
                    CaseProposalVersionModel.organization_id == CaseProposalModel.organization_id,
                    CaseProposalVersionModel.case_id == CaseProposalModel.case_id,
                    CaseProposalVersionModel.proposal_id == CaseProposalModel.id,
                    CaseProposalVersionModel.version == CaseProposalModel.current_version,
                ),
            )
            .outerjoin(
                CaseAnalysisRunModel,
                and_(
                    CaseAnalysisRunModel.organization_id
                    == CaseProposalVersionModel.organization_id,
                    CaseAnalysisRunModel.case_id == CaseProposalVersionModel.case_id,
                    CaseAnalysisRunModel.id == CaseProposalVersionModel.analysis_run_id,
                ),
            )
            .outerjoin(
                ProposalResponseDraftModel,
                and_(
                    ProposalResponseDraftModel.organization_id
                    == CaseProposalVersionModel.organization_id,
                    ProposalResponseDraftModel.case_id == CaseProposalVersionModel.case_id,
                    ProposalResponseDraftModel.proposal_version_id == CaseProposalVersionModel.id,
                ),
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
        ).one_or_none()
        if row is None:
            return None
        proposal, version, run, draft = row
        if version is None or run is None or draft is None:
            raise ProposalSnapshotMismatch("The latest decision brief snapshot is incomplete.")
        return self._assemble_brief(
            proposal=proposal,
            version=version,
            run=run,
            draft=draft,
        )

    def get_version(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        version: int,
    ) -> DecisionBriefRecord | None:
        scoped = self.scoped_case(organization_public_id, case_public_id)
        if scoped is None:
            return None
        _, case = scoped
        proposal = self._session.scalar(
            select(CaseProposalModel).where(
                CaseProposalModel.organization_id == case.organization_id,
                CaseProposalModel.case_id == case.id,
            )
        )
        if proposal is None:
            return None
        version_exists = self._session.scalar(
            select(CaseProposalVersionModel.id).where(
                CaseProposalVersionModel.organization_id == case.organization_id,
                CaseProposalVersionModel.case_id == case.id,
                CaseProposalVersionModel.proposal_id == proposal.id,
                CaseProposalVersionModel.version == version,
            )
        )
        return self.load_brief(proposal, version) if version_exists is not None else None

    def get_by_input_fingerprint(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        input_fingerprint: str,
    ) -> DecisionBriefRecord | None:
        scoped = self.scoped_case(organization_public_id, case_public_id)
        if scoped is None:
            return None
        _, case = scoped
        return self.load_by_input_fingerprint(
            case=case,
            input_fingerprint=input_fingerprint,
        )

    def load_by_input_fingerprint(
        self,
        *,
        case: CaseModel,
        input_fingerprint: str,
    ) -> DecisionBriefRecord | None:
        existing_run = self._session.scalar(
            select(CaseAnalysisRunModel).where(
                CaseAnalysisRunModel.organization_id == case.organization_id,
                CaseAnalysisRunModel.case_id == case.id,
                CaseAnalysisRunModel.input_fingerprint == input_fingerprint,
            )
        )
        if existing_run is None:
            return None
        existing_version = self._session.scalar(
            select(CaseProposalVersionModel).where(
                CaseProposalVersionModel.organization_id == case.organization_id,
                CaseProposalVersionModel.case_id == case.id,
                CaseProposalVersionModel.analysis_run_id == existing_run.id,
            )
        )
        if existing_version is None:
            raise ProposalSnapshotMismatch(
                "The analysis run exists without its immutable proposal snapshot."
            )
        proposal = self._session.get(CaseProposalModel, existing_version.proposal_id)
        if proposal is None or proposal.organization_id != case.organization_id:
            raise ProposalSnapshotMismatch("The proposal root for this analysis is missing.")
        return self.load_brief(proposal, existing_version.version)

    def load_brief(
        self,
        proposal: CaseProposalModel,
        version_number: int,
    ) -> DecisionBriefRecord:
        row = self._session.execute(
            select(
                CaseProposalVersionModel,
                CaseAnalysisRunModel,
                ProposalResponseDraftModel,
            )
            .outerjoin(
                CaseAnalysisRunModel,
                and_(
                    CaseAnalysisRunModel.organization_id
                    == CaseProposalVersionModel.organization_id,
                    CaseAnalysisRunModel.case_id == CaseProposalVersionModel.case_id,
                    CaseAnalysisRunModel.id == CaseProposalVersionModel.analysis_run_id,
                ),
            )
            .outerjoin(
                ProposalResponseDraftModel,
                and_(
                    ProposalResponseDraftModel.organization_id
                    == CaseProposalVersionModel.organization_id,
                    ProposalResponseDraftModel.case_id == CaseProposalVersionModel.case_id,
                    ProposalResponseDraftModel.proposal_version_id == CaseProposalVersionModel.id,
                ),
            )
            .where(
                CaseProposalVersionModel.organization_id == proposal.organization_id,
                CaseProposalVersionModel.case_id == proposal.case_id,
                CaseProposalVersionModel.proposal_id == proposal.id,
                CaseProposalVersionModel.version == version_number,
            )
        ).one_or_none()
        if row is None:
            raise ProposalSnapshotMismatch("The proposal version snapshot is missing.")
        version, run, draft = row
        if run is None or draft is None:
            raise ProposalSnapshotMismatch("The decision brief snapshot is incomplete.")
        return self._assemble_brief(
            proposal=proposal,
            version=version,
            run=run,
            draft=draft,
        )

    def scoped_case(
        self,
        organization_public_id: str,
        case_public_id: str,
    ) -> tuple[OrganizationModel, CaseModel] | None:
        row = self._session.execute(
            select(OrganizationModel, CaseModel)
            .join(CaseModel, CaseModel.organization_id == OrganizationModel.id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
        ).one_or_none()
        return (row[0], row[1]) if row is not None else None

    def _assemble_brief(
        self,
        *,
        proposal: CaseProposalModel,
        version: CaseProposalVersionModel,
        run: CaseAnalysisRunModel,
        draft: ProposalResponseDraftModel,
    ) -> DecisionBriefRecord:
        actions = list(
            self._session.scalars(
                select(CaseProposedActionModel)
                .where(
                    CaseProposedActionModel.organization_id == proposal.organization_id,
                    CaseProposedActionModel.case_id == proposal.case_id,
                    CaseProposedActionModel.proposal_version_id == version.id,
                )
                .order_by(CaseProposedActionModel.public_id)
            )
        )
        checkpoints = list(
            self._session.scalars(
                select(CaseAnalysisCheckpointModel)
                .where(
                    CaseAnalysisCheckpointModel.organization_id == proposal.organization_id,
                    CaseAnalysisCheckpointModel.case_id == proposal.case_id,
                    CaseAnalysisCheckpointModel.analysis_run_id == run.id,
                )
                .order_by(CaseAnalysisCheckpointModel.sequence)
            )
        )
        evidence_ids = list(
            self._session.scalars(
                select(CasePolicyEvidenceModel.public_id)
                .join(
                    ProposalEvidenceBindingModel,
                    and_(
                        ProposalEvidenceBindingModel.organization_id
                        == CasePolicyEvidenceModel.organization_id,
                        ProposalEvidenceBindingModel.case_id == CasePolicyEvidenceModel.case_id,
                        ProposalEvidenceBindingModel.evidence_id == CasePolicyEvidenceModel.id,
                    ),
                )
                .where(
                    ProposalEvidenceBindingModel.organization_id == proposal.organization_id,
                    ProposalEvidenceBindingModel.case_id == proposal.case_id,
                    ProposalEvidenceBindingModel.proposal_version_id == version.id,
                )
                .order_by(CasePolicyEvidenceModel.public_id)
            )
        )
        context_ids = list(
            self._session.scalars(
                select(BusinessObjectSnapshotModel.public_id)
                .join(
                    ProposalContextBindingModel,
                    and_(
                        ProposalContextBindingModel.organization_id
                        == BusinessObjectSnapshotModel.organization_id,
                        ProposalContextBindingModel.case_id == BusinessObjectSnapshotModel.case_id,
                        ProposalContextBindingModel.context_id == BusinessObjectSnapshotModel.id,
                    ),
                )
                .where(
                    ProposalContextBindingModel.organization_id == proposal.organization_id,
                    ProposalContextBindingModel.case_id == proposal.case_id,
                    ProposalContextBindingModel.proposal_version_id == version.id,
                )
                .order_by(BusinessObjectSnapshotModel.public_id)
            )
        )
        version_record = CaseProposalVersionRecord.model_validate(
            {
                **{
                    column.name: getattr(version, column.name)
                    for column in CaseProposalVersionModel.__table__.columns
                },
                "evidence_ids": evidence_ids,
                "context_snapshot_ids": context_ids,
            }
        )
        return DecisionBriefRecord(
            run=AnalysisRunRecord.model_validate(run),
            proposal=CaseProposalRecord.model_validate(proposal),
            version=version_record,
            proposed_actions=[ProposedActionRecord.model_validate(action) for action in actions],
            response_draft=SuggestedResponseRecord.model_validate(draft),
            checkpoints=[
                AnalysisCheckpointRecord.model_validate(checkpoint) for checkpoint in checkpoints
            ],
        )
