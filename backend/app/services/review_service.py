import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from app.analysis.deterministic_decision_engine import (
    combined_context_fingerprint,
    combined_evidence_fingerprint,
)
from app.domain.cases import (
    BusinessObjectRecord,
    CaseConcurrencyConflict,
    CaseStatus,
    CaseWorkspaceRecord,
)
from app.domain.decision_briefs import DecisionBriefRecord
from app.domain.identity import ActorContext, Permission
from app.domain.policies import EvidenceRetrievalResult, PolicyEvidenceBundle
from app.domain.reviews import (
    ReviewAuthorityDenied,
    ReviewBundleRecord,
    ReviewConflict,
    ReviewDecision,
    ReviewDetailRecord,
    ReviewFreshness,
    ReviewFreshnessRecord,
    ReviewNotFound,
    ReviewPageRecord,
    ReviewPolicyState,
    ReviewSnapshotStale,
    ReviewStatus,
    ReviewSubmission,
    ReviewSubmissionNotAllowed,
)
from app.domain.settings import (
    DEFAULT_ADMINISTRATOR_FINANCIAL_LIMITS,
    ApprovalSettingsValues,
)
from app.security.authorization import require_permission
from app.security.review_authority import (
    allowed_decisions,
    approval_is_safe,
    assess_review_rule,
    require_decision_allowed,
    require_review_submission,
    review_policy_state,
    review_uncertainty,
    role_satisfies,
)

TERMINAL_REVIEW_STATUSES = frozenset(
    {
        ReviewStatus.APPROVED,
        ReviewStatus.CHANGES_REQUESTED,
        ReviewStatus.REJECTED,
        ReviewStatus.ESCALATED,
    }
)


class ReviewStore(Protocol):
    def get_for_proposal(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        proposal_version: int,
    ) -> ReviewBundleRecord | None: ...

    def get(
        self, *, organization_public_id: str, review_public_id: str
    ) -> ReviewBundleRecord | None: ...

    def list(
        self,
        *,
        organization_public_id: str,
        status: str | None,
        policy_state: str | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ReviewPageRecord: ...

    def submit(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        command: ReviewSubmission,
        correlation_id: str,
    ) -> ReviewBundleRecord: ...

    def reserve(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
        actor_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> ReviewBundleRecord: ...

    def decide(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
        actor_id: str,
        expected_version: int,
        snapshot_fingerprint: str,
        decision: ReviewDecision,
        reason: str,
        correlation_id: str,
    ) -> ReviewBundleRecord: ...

    def freshness(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
    ) -> ReviewFreshnessRecord: ...


class ReviewCaseStore(Protocol):
    def get_workspace(
        self, *, organization_public_id: str, case_public_id: str
    ) -> CaseWorkspaceRecord | None: ...


class ReviewDecisionStore(Protocol):
    def get_version(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        version: int,
    ) -> DecisionBriefRecord | None: ...


class ReviewPolicyStore(Protocol):
    def list_evidence_for_case(
        self, *, organization_public_id: str, case_public_id: str
    ) -> list[PolicyEvidenceBundle]: ...


class ReviewEvidenceResolver(Protocol):
    def refresh_for_case(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        correlation_id: str,
    ) -> EvidenceRetrievalResult: ...


class ApprovedActionMaterializer(Protocol):
    def materialize(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
        correlation_id: str,
    ) -> None: ...


class ReviewApprovalSettingsProvider(Protocol):
    def approval_values(
        self,
        *,
        organization_public_id: str,
    ) -> tuple[ApprovalSettingsValues, int]: ...


class ReviewService:
    def __init__(
        self,
        store: ReviewStore,
        case_store: ReviewCaseStore,
        decision_store: ReviewDecisionStore,
        policy_store: ReviewPolicyStore,
        evidence_resolver: ReviewEvidenceResolver,
        action_materializer: ApprovedActionMaterializer | None = None,
        approval_settings: ReviewApprovalSettingsProvider | None = None,
    ) -> None:
        self._store = store
        self._case_store = case_store
        self._decision_store = decision_store
        self._policy_store = policy_store
        self._evidence_resolver = evidence_resolver
        self._action_materializer = action_materializer
        self._approval_settings = approval_settings

    def submit(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        proposal_version: int,
        expected_case_version: int,
        correlation_id: str,
    ) -> ReviewDetailRecord:
        require_permission(actor, Permission.CASE_MANAGE)
        require_permission(actor, Permission.REVIEW_READ)
        existing = self._store.get_for_proposal(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            proposal_version=proposal_version,
        )
        if existing is not None:
            return self._detail(actor=actor, bundle=existing)

        workspace = self._case_store.get_workspace(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )
        if workspace is None:
            raise ReviewNotFound("The case was not found.")
        if workspace.case.version != expected_case_version:
            raise CaseConcurrencyConflict(
                expected_version=expected_case_version,
                current_version=workspace.case.version,
            )
        if workspace.case.status is CaseStatus.COMPLETED:
            raise ReviewConflict("A completed case cannot be submitted for review.")
        if workspace.case.status not in {
            CaseStatus.INVESTIGATING,
            CaseStatus.IN_PROGRESS,
        }:
            raise ReviewSubmissionNotAllowed(
                "Move this case into investigation before submitting it for review."
            )
        brief = self._decision_store.get_version(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            version=proposal_version,
        )
        if brief is None:
            raise ReviewNotFound("The proposal version was not found.")
        if brief.proposal.current_version != proposal_version:
            raise ReviewSnapshotStale(
                "A newer resolution exists. Submit the current resolution for review."
            )
        if brief.run.case_version != expected_case_version:
            raise ReviewSnapshotStale(
                "The case changed after this resolution was prepared. Revise the resolution first."
            )
        require_review_submission(brief)

        evidence = self._evidence_resolver.refresh_for_case(
            actor=actor,
            case_id=case_id,
            correlation_id=correlation_id,
        )
        current_context_fingerprint = combined_context_fingerprint(workspace)
        current_evidence_fingerprint = combined_evidence_fingerprint(evidence)
        if current_context_fingerprint != brief.version.context_fingerprint:
            raise ReviewSnapshotStale(
                "Business context changed after this resolution was prepared."
            )
        if (
            current_evidence_fingerprint != brief.version.evidence_fingerprint
            or evidence.status is not brief.run.policy_status
        ):
            raise ReviewSnapshotStale("Policy support changed after this resolution was prepared.")

        approval_settings, approval_rule_version = self._current_approval_settings(
            actor.organization_id
        )
        rule = assess_review_rule(
            brief,
            financial_limits=approval_settings.administrator_financial_limits,
            rule_version=approval_rule_version,
        )
        policy_state = review_policy_state(brief)
        proposal_fingerprint = proposal_snapshot_fingerprint(brief)
        snapshot_fingerprint = review_snapshot_fingerprint(
            case_id=case_id,
            case_version=expected_case_version + 1,
            brief=brief,
            proposal_fingerprint=proposal_fingerprint,
            approval_rule_id=rule.public_id,
            approval_rule_version=rule.version,
        )
        execution_eligible = (
            policy_state is ReviewPolicyState.SUPPORTED
            and approval_is_safe(brief)
            and any(action.review_required for action in brief.proposed_actions)
        )
        bundle = self._store.submit(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            command=ReviewSubmission(
                expected_case_version=expected_case_version,
                proposal_version=proposal_version,
                review_reason=rule.explanation,
                policy_state=policy_state,
                uncertainty=review_uncertainty(brief),
                impact_amount=brief.version.impact_amount,
                impact_currency=brief.version.impact_currency,
                proposal_fingerprint=proposal_fingerprint,
                context_fingerprint=brief.version.context_fingerprint,
                evidence_fingerprint=brief.version.evidence_fingerprint,
                risk_fingerprint=brief.version.risk_fingerprint,
                risk_rule_version=brief.version.risk_rule_version,
                snapshot_fingerprint=snapshot_fingerprint,
                approval_rule=rule,
                execution_eligible=execution_eligible,
            ),
            correlation_id=correlation_id,
        )
        return self._detail(actor=actor, bundle=bundle)

    def list(
        self,
        *,
        actor: ActorContext,
        status: str | None,
        policy_state: str | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ReviewPageRecord:
        require_permission(actor, Permission.REVIEW_READ)
        return self._store.list(
            organization_public_id=actor.organization_id,
            status=status,
            policy_state=policy_state,
            query=query,
            cursor=cursor,
            limit=limit,
        )

    def get(self, *, actor: ActorContext, review_id: str) -> ReviewDetailRecord:
        require_permission(actor, Permission.REVIEW_READ)
        bundle = self._store.get(
            organization_public_id=actor.organization_id,
            review_public_id=review_id,
        )
        if bundle is None:
            raise ReviewNotFound("The review was not found.")
        return self._detail(actor=actor, bundle=bundle)

    def reserve(
        self,
        *,
        actor: ActorContext,
        review_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> ReviewDetailRecord:
        require_permission(actor, Permission.REVIEW_RESERVE)
        current = self.get(actor=actor, review_id=review_id)
        self._require_current(current)
        if not role_satisfies(
            actor_role=actor.role,
            required_role=current.bundle.snapshot.required_role,
        ):
            raise ReviewAuthorityDenied("Your role does not have authority to reserve this review.")
        bundle = self._store.reserve(
            organization_public_id=actor.organization_id,
            review_public_id=review_id,
            actor_id=actor.actor_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
        )
        return self._detail(actor=actor, bundle=bundle)

    def decide(
        self,
        *,
        actor: ActorContext,
        review_id: str,
        expected_version: int,
        snapshot_fingerprint: str,
        decision: ReviewDecision,
        reason: str,
        correlation_id: str,
    ) -> ReviewDetailRecord:
        require_permission(actor, Permission.REVIEW_DECIDE)
        current = self.get(actor=actor, review_id=review_id)
        self._require_current(current)
        if current.bundle.snapshot.snapshot_fingerprint != snapshot_fingerprint:
            raise ReviewConflict("The decision does not match this review snapshot.")
        if not role_satisfies(
            actor_role=actor.role,
            required_role=current.bundle.snapshot.required_role,
        ):
            raise ReviewAuthorityDenied("Your role does not have authority to decide this review.")
        require_decision_allowed(
            decision=decision,
            available_decisions=allowed_decisions(
                brief=current.brief,
                actor_role=actor.role,
                required_role=current.bundle.snapshot.required_role,
            ),
        )
        bundle = self._store.decide(
            organization_public_id=actor.organization_id,
            review_public_id=review_id,
            actor_id=actor.actor_id,
            expected_version=expected_version,
            snapshot_fingerprint=snapshot_fingerprint,
            decision=decision,
            reason=reason,
            correlation_id=correlation_id,
        )
        if (
            decision is ReviewDecision.APPROVE
            and self._action_materializer is not None
        ):
            self._action_materializer.materialize(
                organization_public_id=actor.organization_id,
                review_public_id=bundle.review.public_id,
                correlation_id=correlation_id,
            )
        return self._detail(actor=actor, bundle=bundle)

    def _detail(self, *, actor: ActorContext, bundle: ReviewBundleRecord) -> ReviewDetailRecord:
        brief = self._decision_store.get_version(
            organization_public_id=actor.organization_id,
            case_public_id=bundle.case_public_id,
            version=bundle.snapshot.proposal_version,
        )
        workspace = self._case_store.get_workspace(
            organization_public_id=actor.organization_id,
            case_public_id=bundle.case_public_id,
        )
        if brief is None or workspace is None:
            raise ReviewNotFound("The reviewed resolution snapshot is unavailable.")
        context_ids = set(brief.version.context_snapshot_ids)
        evidence_ids = set(brief.version.evidence_ids)
        contexts: list[BusinessObjectRecord] = [
            context for context in workspace.business_contexts if context.public_id in context_ids
        ]
        evidence: list[PolicyEvidenceBundle] = [
            item
            for item in self._policy_store.list_evidence_for_case(
                organization_public_id=actor.organization_id,
                case_public_id=bundle.case_public_id,
            )
            if item.evidence.public_id in evidence_ids
        ]
        if len(contexts) != len(context_ids) or len(evidence) != len(evidence_ids):
            freshness = ReviewFreshnessRecord(
                status=ReviewFreshness.STALE,
                checked_at=datetime.now(UTC),
                reason="One or more reviewed source records are unavailable.",
            )
        elif proposal_snapshot_fingerprint(brief) != bundle.snapshot.proposal_fingerprint:
            freshness = ReviewFreshnessRecord(
                status=ReviewFreshness.STALE,
                checked_at=datetime.now(UTC),
                reason="The reviewed resolution no longer matches its snapshot.",
            )
        else:
            freshness = self._store.freshness(
                organization_public_id=actor.organization_id,
                review_public_id=bundle.review.public_id,
            )
        _, approval_rule_version = self._current_approval_settings(
            actor.organization_id
        )
        if (
            freshness.status is ReviewFreshness.CURRENT
            and bundle.review.status not in TERMINAL_REVIEW_STATUSES
            and bundle.snapshot.approval_rule_id != "APR-LEGACY"
            and bundle.snapshot.approval_rule_version != approval_rule_version
        ):
            freshness = ReviewFreshnessRecord(
                status=ReviewFreshness.STALE,
                checked_at=datetime.now(UTC),
                reason=(
                    "Approval rules changed after this review was submitted. "
                    "Prepare a new resolution review."
                ),
            )
        decisions: list[ReviewDecision] = []
        if (
            freshness.status is ReviewFreshness.CURRENT
            and bundle.review.status not in TERMINAL_REVIEW_STATUSES
            and actor.can(Permission.REVIEW_DECIDE)
        ):
            decisions = allowed_decisions(
                brief=brief,
                actor_role=actor.role,
                required_role=bundle.snapshot.required_role,
            )
        return ReviewDetailRecord(
            bundle=bundle,
            brief=brief,
            business_contexts=contexts,
            evidence=evidence,
            freshness=freshness,
            available_decisions=decisions,
        )

    def _current_approval_settings(
        self,
        organization_public_id: str,
    ) -> tuple[ApprovalSettingsValues, int]:
        if self._approval_settings is None:
            return (
                ApprovalSettingsValues(
                    administrator_financial_limits=(
                        DEFAULT_ADMINISTRATOR_FINANCIAL_LIMITS
                    )
                ),
                1,
            )
        return self._approval_settings.approval_values(
            organization_public_id=organization_public_id
        )

    @staticmethod
    def _require_current(detail: ReviewDetailRecord) -> None:
        if detail.freshness.status is ReviewFreshness.STALE:
            raise ReviewSnapshotStale(
                detail.freshness.reason or "The review snapshot is stale and cannot be decided."
            )


def proposal_snapshot_fingerprint(brief: DecisionBriefRecord) -> str:
    return _hash(
        {
            "run_input_fingerprint": brief.run.input_fingerprint,
            "version": brief.version.model_dump(mode="json"),
            "actions": [action.model_dump(mode="json") for action in brief.proposed_actions],
            "response_draft": brief.response_draft.model_dump(mode="json"),
        }
    )


def review_snapshot_fingerprint(
    *,
    case_id: str,
    case_version: int,
    brief: DecisionBriefRecord,
    proposal_fingerprint: str,
    approval_rule_id: str,
    approval_rule_version: int,
) -> str:
    return _hash(
        {
            "case_id": case_id,
            "case_version": case_version,
            "proposal_id": brief.proposal.public_id,
            "proposal_version": brief.version.version,
            "proposal_fingerprint": proposal_fingerprint,
            "context_fingerprint": brief.version.context_fingerprint,
            "evidence_fingerprint": brief.version.evidence_fingerprint,
            "risk_fingerprint": brief.version.risk_fingerprint,
            "risk_rule_version": brief.version.risk_rule_version,
            "approval_rule_id": approval_rule_id,
            "approval_rule_version": approval_rule_version,
        }
    )


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
