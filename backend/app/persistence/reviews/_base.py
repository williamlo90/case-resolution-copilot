import base64
import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.domain.decision_briefs import DecisionProposalState
from app.domain.identity import ActorMembershipNotFound, MemberRole
from app.domain.reviews import (
    InvalidReviewCursor,
    ReviewBundleRecord,
    ReviewConflict,
    ReviewDecision,
    ReviewDecisionRecord,
    ReviewFreshness,
    ReviewFreshnessRecord,
    ReviewNotFound,
    ReviewRecord,
    ReviewReservationRecord,
    ReviewReservationStatus,
    ReviewSnapshotRecord,
    ReviewSnapshotStale,
    ReviewStatus,
)
from app.domain.settings import SettingsSection
from app.persistence.models import (
    AuditEventModel,
    BusinessObjectSnapshotModel,
    CaseModel,
    CasePolicyEvidenceModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseReviewDecisionModel,
    CaseReviewModel,
    CaseReviewReservationModel,
    CaseReviewSnapshotModel,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    MembershipModel,
    OrganizationModel,
    OrganizationSettingModel,
    ProposalContextBindingModel,
    ProposalEvidenceBindingModel,
)

REVIEW_HOLD_MINUTES = 30
TERMINAL_REVIEW_STATUSES = frozenset(
    {
        ReviewStatus.APPROVED.value,
        ReviewStatus.CHANGES_REQUESTED.value,
        ReviewStatus.REJECTED.value,
        ReviewStatus.ESCALATED.value,
    }
)


class ReviewRepositoryBase:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _load_bundle(self, review: CaseReviewModel, *, now: datetime) -> ReviewBundleRecord:
        snapshot = self._required_snapshot(review)
        case = self._session.get(CaseModel, review.case_id)
        proposal = self._session.get(CaseProposalModel, review.proposal_id)
        if case is None or proposal is None:
            raise ReviewConflict("The reviewed case or resolution is missing.")
        reservation = self._active_reservation(review, now=now)
        decisions = list(
            self._session.scalars(
                select(CaseReviewDecisionModel)
                .where(
                    CaseReviewDecisionModel.organization_id == review.organization_id,
                    CaseReviewDecisionModel.case_id == review.case_id,
                    CaseReviewDecisionModel.review_id == review.id,
                )
                .order_by(CaseReviewDecisionModel.decided_at)
            )
        )
        return ReviewBundleRecord(
            review=ReviewRecord.model_validate(review),
            snapshot=ReviewSnapshotRecord.model_validate(snapshot),
            case_public_id=case.public_id,
            proposal_public_id=proposal.public_id,
            reservation=(
                ReviewReservationRecord.model_validate(reservation)
                if reservation is not None
                else None
            ),
            decisions=[ReviewDecisionRecord.model_validate(decision) for decision in decisions],
        )

    def _required_snapshot(self, review: CaseReviewModel) -> CaseReviewSnapshotModel:
        snapshot = self._session.scalar(
            select(CaseReviewSnapshotModel).where(
                CaseReviewSnapshotModel.organization_id == review.organization_id,
                CaseReviewSnapshotModel.case_id == review.case_id,
                CaseReviewSnapshotModel.review_id == review.id,
            )
        )
        if snapshot is None:
            raise ReviewConflict("The immutable review snapshot is missing.")
        return snapshot

    def _active_reservation(
        self, review: CaseReviewModel, *, now: datetime
    ) -> CaseReviewReservationModel | None:
        return self._session.scalar(
            select(CaseReviewReservationModel).where(
                CaseReviewReservationModel.organization_id == review.organization_id,
                CaseReviewReservationModel.case_id == review.case_id,
                CaseReviewReservationModel.review_id == review.id,
                CaseReviewReservationModel.status == ReviewReservationStatus.ACTIVE.value,
                CaseReviewReservationModel.expires_at > now,
            )
        )

    def _reconcile_expired(
        self,
        *,
        now: datetime,
        review: CaseReviewModel | None = None,
        organization_id: UUID | None = None,
    ) -> None:
        conditions = [
            CaseReviewReservationModel.status == ReviewReservationStatus.ACTIVE.value,
            CaseReviewReservationModel.expires_at <= now,
        ]
        if review is not None:
            conditions.extend(
                [
                    CaseReviewReservationModel.organization_id == review.organization_id,
                    CaseReviewReservationModel.review_id == review.id,
                ]
            )
        elif organization_id is not None:
            conditions.append(CaseReviewReservationModel.organization_id == organization_id)
        expired = list(
            self._session.scalars(
                select(CaseReviewReservationModel).where(*conditions).with_for_update()
            )
        )
        for reservation in expired:
            reservation.status = ReviewReservationStatus.EXPIRED.value
            target_review = (
                review
                if review is not None and review.id == reservation.review_id
                else self._session.get(CaseReviewModel, reservation.review_id)
            )
            self._session.add(
                AuditEventModel(
                    organization_id=reservation.organization_id,
                    task_id=None,
                    run_id=None,
                    event_type="case.review_reservation_expired",
                    actor_type="system",
                    actor_id="review-expiry-reconciler",
                    subject_type=("review" if target_review is not None else "review_reservation"),
                    subject_id=(
                        target_review.public_id
                        if target_review is not None
                        else reservation.public_id
                    ),
                    summary="Review reservation expired and returned to the queue.",
                    data={
                        "reservation_id": reservation.public_id,
                        "expired_at": reservation.expires_at.isoformat(),
                    },
                    correlation_id=f"review-expiry:{reservation.public_id}",
                    occurred_at=now,
                )
            )
            if target_review is None or target_review.status != ReviewStatus.RESERVED.value:
                continue
            target_review.status = ReviewStatus.PENDING.value
            target_review.version += 1
            target_review.updated_at = now
            self._set_proposal_state(
                target_review,
                self._open_proposal_state(target_review),
                now=now,
            )

    def _set_proposal_state(
        self,
        review: CaseReviewModel,
        state: DecisionProposalState,
        *,
        now: datetime,
    ) -> None:
        proposal = self._session.scalar(
            select(CaseProposalModel)
            .where(
                CaseProposalModel.id == review.proposal_id,
                CaseProposalModel.organization_id == review.organization_id,
            )
            .with_for_update()
        )
        if (
            proposal is None
            or proposal.current_version != self._required_snapshot(review).proposal_version
        ):
            return
        proposal.state = state.value
        proposal.version += 1
        proposal.updated_at = now

    def _open_proposal_state(self, review: CaseReviewModel) -> DecisionProposalState:
        version = self._session.get(
            CaseProposalVersionModel,
            review.proposal_version_id,
        )
        if version is None:
            return DecisionProposalState.INFORMATION_NEEDED
        state = DecisionProposalState(version.state)
        if state in {
            DecisionProposalState.READY_FOR_REVIEW,
            DecisionProposalState.INFORMATION_NEEDED,
        }:
            return state
        return DecisionProposalState.INFORMATION_NEEDED

    def _active_member(
        self,
        *,
        organization_id: UUID,
        actor_id: str,
        for_update: bool = False,
    ) -> MembershipModel:
        statement = select(MembershipModel).where(
                MembershipModel.organization_id == organization_id,
                MembershipModel.status == "active",
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        if for_update:
            statement = statement.with_for_update()
        member = self._session.scalar(statement)
        if member is None:
            raise ActorMembershipNotFound(
                "An active organization membership is required for this review."
            )
        return member

    def _require_approval_rule_version(
        self,
        *,
        organization_id: UUID,
        expected_version: int,
    ) -> None:
        setting = self._session.scalar(
            select(OrganizationSettingModel)
            .where(
                OrganizationSettingModel.organization_id == organization_id,
                OrganizationSettingModel.section == SettingsSection.APPROVALS.value,
            )
            .with_for_update()
        )
        if setting is None:
            organization = self._session.scalar(
                select(OrganizationModel)
                .where(OrganizationModel.id == organization_id)
                .with_for_update()
            )
            if organization is None:
                raise ReviewConflict("The review organization is unavailable.")
            current_version = 1
        else:
            current_version = setting.version
        if current_version != expected_version:
            raise ReviewSnapshotStale(
                "Approval rules changed after this review was submitted. "
                "Prepare a new resolution review."
            )

    def _required_review(
        self,
        organization_public_id: str,
        review_public_id: str,
        *,
        for_update: bool = False,
    ) -> CaseReviewModel:
        review = self._scoped_review(
            organization_public_id,
            review_public_id,
            for_update=for_update,
        )
        if review is None:
            raise ReviewNotFound("The review was not found.")
        return review

    def _scoped_review(
        self,
        organization_public_id: str,
        review_public_id: str,
        *,
        for_update: bool = False,
    ) -> CaseReviewModel | None:
        statement = (
            select(CaseReviewModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == CaseReviewModel.organization_id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseReviewModel.public_id == review_public_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _scoped_case(
        self,
        organization_public_id: str,
        case_public_id: str,
        *,
        for_update: bool = False,
    ) -> tuple[OrganizationModel, CaseModel] | None:
        statement = (
            select(OrganizationModel, CaseModel)
            .join(CaseModel, CaseModel.organization_id == OrganizationModel.id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).one_or_none()
        return (row[0], row[1]) if row is not None else None

    def _freshness(
        self,
        review: CaseReviewModel,
        *,
        now: datetime,
        for_update: bool = False,
    ) -> ReviewFreshnessRecord:
        snapshot = self._required_snapshot(review)
        if snapshot.approval_rule_id == "APR-LEGACY":
            return _stale(now, "Historical approvals require a new governed review.")
        case_statement = select(CaseModel).where(CaseModel.id == review.case_id)
        proposal_statement = select(CaseProposalModel).where(
            CaseProposalModel.id == review.proposal_id
        )
        version_statement = select(CaseProposalVersionModel).where(
            CaseProposalVersionModel.id == review.proposal_version_id
        )
        if for_update:
            case_statement = case_statement.with_for_update()
            proposal_statement = proposal_statement.with_for_update()
            version_statement = version_statement.with_for_update()
        case = self._session.scalar(case_statement)
        proposal = self._session.scalar(proposal_statement)
        version = self._session.scalar(version_statement)
        if case is None or proposal is None or version is None:
            return _stale(now, "The reviewed case or resolution snapshot is unavailable.")
        if case.version != snapshot.case_version:
            return _stale(now, "The case changed after this review was submitted.")
        if proposal.current_version != snapshot.proposal_version:
            return _stale(now, "A newer resolution version is available.")
        if (
            version.context_fingerprint != snapshot.context_fingerprint
            or version.evidence_fingerprint != snapshot.evidence_fingerprint
            or version.risk_fingerprint != snapshot.risk_fingerprint
            or version.risk_rule_version != snapshot.risk_rule_version
        ):
            return _stale(now, "The reviewed resolution bindings no longer match.")
        context_statement = (
            select(
                ProposalContextBindingModel,
                BusinessObjectSnapshotModel,
            )
            .join(
                BusinessObjectSnapshotModel,
                and_(
                    BusinessObjectSnapshotModel.organization_id
                    == ProposalContextBindingModel.organization_id,
                    BusinessObjectSnapshotModel.case_id == ProposalContextBindingModel.case_id,
                    BusinessObjectSnapshotModel.id == ProposalContextBindingModel.context_id,
                ),
            )
            .where(
                ProposalContextBindingModel.organization_id == review.organization_id,
                ProposalContextBindingModel.case_id == review.case_id,
                ProposalContextBindingModel.proposal_version_id == review.proposal_version_id,
            )
        )
        if for_update:
            context_statement = context_statement.with_for_update()
        context_rows = self._session.execute(context_statement).all()
        if not context_rows:
            return _stale(now, "The reviewed business context is unavailable.")
        current_context_material: list[dict[str, str]] = []
        for binding, context in context_rows:
            current_fingerprint = _context_fingerprint(context)
            if (
                context.version != binding.snapshot_version
                or current_fingerprint != binding.context_fingerprint
            ):
                return _stale(
                    now,
                    "Business context changed after this review was submitted.",
                )
            current_context_material.append(
                {
                    "id": context.public_id,
                    "fingerprint": current_fingerprint,
                }
            )
        if (
            _hash(
                sorted(
                    current_context_material,
                    key=lambda item: item["id"],
                )
            )
            != snapshot.context_fingerprint
        ):
            return _stale(now, "The reviewed business context binding changed.")
        if review.policy_state == "supported":
            evidence_statement = (
                select(
                    ProposalEvidenceBindingModel,
                    CasePolicyEvidenceModel,
                    GovernedPolicyVersionModel,
                    GovernedPolicyClauseModel,
                )
                .join(
                    CasePolicyEvidenceModel,
                    and_(
                        CasePolicyEvidenceModel.organization_id
                        == ProposalEvidenceBindingModel.organization_id,
                        CasePolicyEvidenceModel.case_id == ProposalEvidenceBindingModel.case_id,
                        CasePolicyEvidenceModel.id == ProposalEvidenceBindingModel.evidence_id,
                    ),
                )
                .join(
                    GovernedPolicyVersionModel,
                    and_(
                        GovernedPolicyVersionModel.organization_id
                        == CasePolicyEvidenceModel.organization_id,
                        GovernedPolicyVersionModel.id == CasePolicyEvidenceModel.policy_version_id,
                    ),
                )
                .join(
                    GovernedPolicyClauseModel,
                    and_(
                        GovernedPolicyClauseModel.organization_id
                        == CasePolicyEvidenceModel.organization_id,
                        GovernedPolicyClauseModel.id == CasePolicyEvidenceModel.clause_id,
                    ),
                )
                .where(
                    ProposalEvidenceBindingModel.organization_id == review.organization_id,
                    ProposalEvidenceBindingModel.case_id == review.case_id,
                    ProposalEvidenceBindingModel.proposal_version_id == review.proposal_version_id,
                )
            )
            if for_update:
                evidence_statement = evidence_statement.with_for_update()
            evidence_rows = self._session.execute(evidence_statement).all()
            if not evidence_rows:
                return _stale(now, "The reviewed policy evidence is unavailable.")
            evidence_fingerprints: list[str] = []
            for binding, evidence, policy, clause in evidence_rows:
                if (
                    binding.evidence_fingerprint != evidence.fingerprint
                    or evidence.freshness != "current"
                    or evidence.conflict_state != "none"
                    or evidence.policy_content_hash != policy.content_hash
                    or evidence.clause_content_hash != clause.content_hash
                ):
                    return _stale(
                        now,
                        "The reviewed policy evidence binding changed.",
                    )
                evidence_fingerprints.append(evidence.fingerprint)
                if (
                    policy.status != "published"
                    or policy.effective_from is None
                    or policy.effective_from > now
                    or (policy.effective_to is not None and policy.effective_to <= now)
                ):
                    return _stale(
                        now,
                        "Policy authority changed after this review was submitted.",
                    )
            if (
                _hash(
                    {
                        "status": "relevant",
                        "evidence": sorted(evidence_fingerprints),
                    }
                )
                != snapshot.evidence_fingerprint
            ):
                return _stale(now, "The reviewed policy evidence set changed.")
        return ReviewFreshnessRecord(
            status=ReviewFreshness.CURRENT,
            checked_at=now,
            reason=None,
        )


def _review_status(decision: ReviewDecision) -> ReviewStatus:
    return {
        ReviewDecision.APPROVE: ReviewStatus.APPROVED,
        ReviewDecision.REQUEST_CHANGES: ReviewStatus.CHANGES_REQUESTED,
        ReviewDecision.REJECT: ReviewStatus.REJECTED,
        ReviewDecision.ESCALATE: ReviewStatus.ESCALATED,
    }[decision]


def _proposal_state(decision: ReviewDecision) -> DecisionProposalState:
    return {
        ReviewDecision.APPROVE: DecisionProposalState.APPROVED,
        ReviewDecision.REQUEST_CHANGES: DecisionProposalState.INFORMATION_NEEDED,
        ReviewDecision.REJECT: DecisionProposalState.REJECTED,
        ReviewDecision.ESCALATE: DecisionProposalState.UNDER_REVIEW,
    }[decision]


def _decision_label(decision: ReviewDecision) -> str:
    return {
        ReviewDecision.APPROVE: "approved",
        ReviewDecision.REQUEST_CHANGES: "changes requested",
        ReviewDecision.REJECT: "rejected",
        ReviewDecision.ESCALATE: "escalated",
    }[decision]


def _legacy_role(value: str) -> MemberRole | None:
    return {
        "operator": MemberRole.SPECIALIST,
        "supervisor": MemberRole.SUPERVISOR,
        "administrator": MemberRole.ADMINISTRATOR,
        "auditor": MemberRole.AUDITOR,
    }.get(value)


def _legacy_decision(value: str) -> ReviewDecision | None:
    return {
        "approved": ReviewDecision.APPROVE,
        "rejected": ReviewDecision.REJECT,
        "needs_information": ReviewDecision.REQUEST_CHANGES,
    }.get(value)


def _stale(now: datetime, reason: str) -> ReviewFreshnessRecord:
    return ReviewFreshnessRecord(
        status=ReviewFreshness.STALE,
        checked_at=now,
        reason=reason,
    )


def _stable_public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _context_fingerprint(context: BusinessObjectSnapshotModel) -> str:
    return _hash(
        {
            "public_id": context.public_id,
            "version": context.version,
            "type": context.object_type,
            "status": context.status,
            "source": context.source,
            "source_reference": context.source_reference,
            "fields": dict(sorted((key, str(value)) for key, value in context.fields.items())),
            "captured_at": context.captured_at.isoformat(),
            "source_freshness": context.source_freshness,
            "source_checked_at": (
                context.source_checked_at.isoformat() if context.source_checked_at else None
            ),
        }
    )


def _encode_cursor(
    submitted_at: datetime,
    public_id: str,
    filter_fingerprint: str,
) -> str:
    payload = json.dumps(
        {
            "submitted_at": submitted_at.astimezone(UTC).isoformat(),
            "public_id": public_id,
            "filter": filter_fingerprint,
        },
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str, expected_filter: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        submitted_at = datetime.fromisoformat(payload["submitted_at"])
        public_id = str(payload["public_id"])
        filter_fingerprint = str(payload["filter"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidReviewCursor("The review cursor is invalid.") from exc
    if submitted_at.tzinfo is None or filter_fingerprint != expected_filter:
        raise InvalidReviewCursor("The review cursor does not match these filters.")
    return submitted_at.astimezone(UTC), public_id
