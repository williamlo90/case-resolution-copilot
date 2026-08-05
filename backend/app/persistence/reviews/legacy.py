from sqlalchemy import select

from app.domain.identity import MemberRole
from app.domain.reviews import (
    LegacyReviewImport,
    ReviewBundleRecord,
    ReviewConflict,
    ReviewNotFound,
    ReviewReservationStatus,
    ReviewStatus,
)
from app.persistence.models import (
    ApprovalDecisionModel,
    AuditEventModel,
    CaseModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseReviewDecisionModel,
    CaseReviewModel,
    CaseReviewReservationModel,
    CaseReviewSnapshotModel,
    OrganizationModel,
    ReviewerReservationModel,
    utc_now,
)

from ._base import (
    ReviewRepositoryBase,
    _hash,
    _legacy_decision,
    _legacy_role,
    _review_status,
    _stable_public_id,
)


class LegacyReviewRepository(ReviewRepositoryBase):
    def import_legacy(
        self,
        *,
        organization_public_id: str,
        importer_actor_id: str,
        command: LegacyReviewImport,
        correlation_id: str,
    ) -> ReviewBundleRecord:
        version = self._session.scalar(
            select(CaseProposalVersionModel).where(
                CaseProposalVersionModel.legacy_proposal_version_id
                == command.legacy_proposal_version_id
            )
        )
        if version is None:
            raise ReviewNotFound("The legacy proposal must be imported before its review history.")
        if version.version != command.source_proposal_version:
            raise ReviewConflict(
                "The legacy review proposal version does not match its imported proposal."
            )
        self._verify_legacy_lineage(command)
        organization = self._session.scalar(
            select(OrganizationModel).where(
                OrganizationModel.public_id == organization_public_id,
                OrganizationModel.id == version.organization_id,
            )
        )
        if organization is None:
            raise ReviewNotFound("The imported proposal does not belong to this organization.")
        existing = self._session.scalar(
            select(CaseReviewModel).where(
                CaseReviewModel.organization_id == version.organization_id,
                CaseReviewModel.case_id == version.case_id,
                CaseReviewModel.proposal_version_id == version.id,
            )
        )
        if existing is not None:
            return self._load_bundle(existing, now=utc_now())
        case = self._session.get(CaseModel, version.case_id)
        proposal = self._session.get(CaseProposalModel, version.proposal_id)
        if case is None or proposal is None:
            raise ReviewNotFound("The imported generic proposal lineage is incomplete.")
        importer = self._active_member(
            organization_id=organization.id,
            actor_id=importer_actor_id,
        )
        snapshot_fingerprint = _hash(
            {
                "legacy_reservation_id": str(command.legacy_reservation_id),
                "legacy_decision_id": (
                    str(command.legacy_decision_id)
                    if command.legacy_decision_id is not None
                    else None
                ),
                "legacy_proposal_version_id": str(command.legacy_proposal_version_id),
                "source_evidence_fingerprint": command.source_evidence_fingerprint,
            }
        )
        review_status = (
            _review_status(command.decision)
            if command.decision is not None
            else ReviewStatus.PENDING
        )
        now = command.decided_at or command.reserved_at
        review = CaseReviewModel(
            public_id=_stable_public_id("RV-LEGACY", str(command.legacy_reservation_id)),
            organization_id=organization.id,
            case_id=case.id,
            proposal_id=proposal.id,
            proposal_version_id=version.id,
            status=review_status.value,
            review_reason=(
                "Imported historical review. Fresh governed review is required before execution."
            ),
            policy_state="missing",
            uncertainty="high",
            impact_amount=version.impact_amount,
            impact_currency=version.impact_currency,
            submitted_by_id=importer.id,
            submitted_by_public_id=importer.public_id,
            submitted_by_name=importer.name,
            submitted_by_role=importer.role,
            submitted_at=command.reserved_at,
            version=1,
            updated_at=now,
        )
        self._session.add(review)
        self._session.flush()
        snapshot = CaseReviewSnapshotModel(
            public_id=_stable_public_id("RVS-LEGACY", review.public_id),
            organization_id=organization.id,
            case_id=case.id,
            review_id=review.id,
            proposal_id=proposal.id,
            proposal_version_id=version.id,
            case_version=case.version,
            proposal_version=version.version,
            proposal_fingerprint=_hash({"legacy_proposal": str(version.id)}),
            context_fingerprint=version.context_fingerprint,
            evidence_fingerprint=version.evidence_fingerprint,
            risk_fingerprint=version.risk_fingerprint,
            risk_rule_version=version.risk_rule_version,
            snapshot_fingerprint=snapshot_fingerprint,
            approval_rule_id="APR-LEGACY",
            approval_rule_name="Historical review record",
            approval_rule_explanation=(
                "This imported decision does not authorize a current action."
            ),
            required_role=MemberRole.ADMINISTRATOR.value,
            approval_rule_version=1,
            execution_eligible=False,
            created_at=command.reserved_at,
        )
        self._session.add(snapshot)
        self._session.flush()
        reservation = CaseReviewReservationModel(
            public_id=_stable_public_id("RVR-LEGACY", str(command.legacy_reservation_id)),
            organization_id=organization.id,
            case_id=case.id,
            review_id=review.id,
            snapshot_id=snapshot.id,
            reviewer_id=None,
            legacy_reservation_id=command.legacy_reservation_id,
            reviewer_public_id=command.reviewer_public_id[:64],
            reviewer_name=command.reviewer_name[:200],
            reviewer_role=command.reviewer_role.value,
            snapshot_fingerprint=snapshot_fingerprint,
            status=(
                ReviewReservationStatus.CONSUMED.value
                if command.decision is not None
                else ReviewReservationStatus.EXPIRED.value
            ),
            reserved_at=command.reserved_at,
            expires_at=command.expires_at,
            consumed_at=command.decided_at,
        )
        self._session.add(reservation)
        self._session.flush()
        if command.decision is not None and command.decided_at is not None:
            self._session.add(
                CaseReviewDecisionModel(
                    public_id=_stable_public_id("RVD-LEGACY", str(command.legacy_decision_id)),
                    organization_id=organization.id,
                    case_id=case.id,
                    review_id=review.id,
                    reservation_id=reservation.id,
                    reviewer_id=None,
                    legacy_decision_id=command.legacy_decision_id,
                    reviewer_public_id=command.reviewer_public_id[:64],
                    reviewer_name=command.reviewer_name[:200],
                    reviewer_role=command.reviewer_role.value,
                    decision=command.decision.value,
                    reason=command.reason,
                    snapshot_fingerprint=snapshot_fingerprint,
                    decided_at=command.decided_at,
                )
            )
        self._session.add(
            AuditEventModel(
                organization_id=organization.id,
                task_id=None,
                run_id=None,
                event_type="case.legacy_review_imported",
                actor_type="system",
                actor_id=importer.public_id,
                subject_type="review",
                subject_id=review.public_id,
                summary="Historical review imported without current execution authority.",
                data={
                    "legacy_reservation_id": str(command.legacy_reservation_id),
                    "legacy_decision_id": (
                        str(command.legacy_decision_id)
                        if command.legacy_decision_id is not None
                        else None
                    ),
                    "snapshot_fingerprint": snapshot_fingerprint,
                    "execution_eligible": False,
                },
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )
        self._session.flush()
        return self._load_bundle(review, now=utc_now())

    def _verify_legacy_lineage(self, command: LegacyReviewImport) -> None:
        reservation = self._session.get(
            ReviewerReservationModel,
            command.legacy_reservation_id,
        )
        if (
            reservation is None
            or reservation.proposal_id != command.legacy_proposal_version_id
            or reservation.proposal_version != command.source_proposal_version
            or reservation.evidence_fingerprint != command.source_evidence_fingerprint
            or reservation.reviewer_id != command.reviewer_name
            or _legacy_role(reservation.reviewer_role) is not command.reviewer_role
        ):
            raise ReviewConflict(
                "The legacy reservation does not match the imported review lineage."
            )
        if command.legacy_decision_id is None:
            return
        decision = self._session.get(
            ApprovalDecisionModel,
            command.legacy_decision_id,
        )
        if (
            decision is None
            or decision.proposal_id != command.legacy_proposal_version_id
            or decision.reservation_id != command.legacy_reservation_id
            or decision.proposal_version != command.source_proposal_version
            or decision.evidence_fingerprint != command.source_evidence_fingerprint
            or decision.reviewer_id != command.reviewer_name
            or _legacy_role(decision.reviewer_role) is not command.reviewer_role
            or _legacy_decision(decision.outcome) is not command.decision
            or decision.decided_at != command.decided_at
        ):
            raise ReviewConflict("The legacy decision does not match the imported review lineage.")
