from datetime import timedelta

from sqlalchemy import select

from app.domain.actions import (
    ActionAttemptCommand,
    ActionBundleRecord,
    ActionConflict,
    ActionExecutionBlocker,
    ActionNotFound,
    ActionQueueItemRecord,
    ActionStatus,
    LegacyActionImport,
)
from app.persistence.connection_repository import ConnectionRepository
from app.persistence.models import (
    AuditEventModel,
    CaseActionAttemptModel,
    CaseActionModel,
    CaseActionReceiptModel,
    CaseModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseProposedActionModel,
    CaseReviewDecisionModel,
    CaseReviewModel,
    MembershipModel,
    OrganizationModel,
    utc_now,
)

from ._base import (
    ACTION_AUTHORIZATION_HOURS,
    ActionRepositoryBase,
    _action_target,
    _hash,
    _materialization_blocker,
    _stable_public_id,
)


class ActionMaterializationRepository(ActionRepositoryBase):
    def materialize_approved_review(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
        correlation_id: str,
    ) -> list[ActionBundleRecord]:
        review = self._session.scalar(
            select(CaseReviewModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == CaseReviewModel.organization_id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseReviewModel.public_id == review_public_id,
            )
            .with_for_update()
        )
        if review is None:
            raise ActionNotFound("The approved review was not found.")
        if review.status != "approved":
            raise ActionConflict("Actions can only be created from an approved review.")
        snapshot = self._required_review_snapshot(review)
        decision = self._session.scalar(
            select(CaseReviewDecisionModel).where(
                CaseReviewDecisionModel.organization_id == review.organization_id,
                CaseReviewDecisionModel.case_id == review.case_id,
                CaseReviewDecisionModel.review_id == review.id,
                CaseReviewDecisionModel.decision == "approve",
            )
        )
        case = self._session.get(CaseModel, review.case_id)
        proposal = self._session.get(CaseProposalModel, review.proposal_id)
        version = self._session.get(
            CaseProposalVersionModel,
            review.proposal_version_id,
        )
        if decision is None or case is None or proposal is None or version is None:
            raise ActionConflict(
                "The approved review lineage is incomplete; no action was created."
            )
        if decision.snapshot_fingerprint != snapshot.snapshot_fingerprint:
            raise ActionConflict(
                "The approval decision does not match the immutable review snapshot."
            )
        proposed_actions = list(
            self._session.scalars(
                select(CaseProposedActionModel)
                .where(
                    CaseProposedActionModel.organization_id == review.organization_id,
                    CaseProposedActionModel.case_id == review.case_id,
                    CaseProposedActionModel.proposal_id == review.proposal_id,
                    CaseProposedActionModel.proposal_version_id == review.proposal_version_id,
                    CaseProposedActionModel.review_required.is_(True),
                )
                .order_by(
                    CaseProposedActionModel.created_at,
                    CaseProposedActionModel.public_id,
                )
            )
        )
        owner = (
            self._session.get(MembershipModel, case.owner_id) if case.owner_id is not None else None
        )
        now = utc_now()
        created: list[CaseActionModel] = []
        connection_repository = ConnectionRepository(self._session)
        for proposed_action in proposed_actions:
            existing = self._session.scalar(
                select(CaseActionModel).where(
                    CaseActionModel.organization_id == review.organization_id,
                    CaseActionModel.case_id == review.case_id,
                    CaseActionModel.proposed_action_id == proposed_action.id,
                )
            )
            if existing is not None:
                created.append(existing)
                continue
            connection = connection_repository.resolve_for_action(
                organization_id=review.organization_id,
                organization_public_id=organization_public_id,
                action_type=proposed_action.type,
            )
            execution_eligible = bool(
                snapshot.execution_eligible
                and version.legacy_proposal_version_id is None
                and case.version == snapshot.case_version
                and proposal.current_version == snapshot.proposal_version
                and proposal.state == "approved"
            )
            blocker = _materialization_blocker(
                execution_eligible=execution_eligible,
                connection=connection,
                now=now,
            )
            action = CaseActionModel(
                public_id=_stable_public_id(
                    "AC",
                    organization_public_id,
                    proposed_action.public_id,
                    snapshot.snapshot_fingerprint,
                ),
                organization_id=review.organization_id,
                case_id=review.case_id,
                proposal_id=review.proposal_id,
                proposal_version_id=review.proposal_version_id,
                proposed_action_id=proposed_action.id,
                review_id=review.id,
                review_snapshot_id=snapshot.id,
                review_decision_id=decision.id,
                connection_id=connection.id,
                legacy_proposal_version_id=version.legacy_proposal_version_id,
                type=proposed_action.type,
                label=proposed_action.label,
                target=_action_target(proposed_action, case),
                typed_parameters=dict(proposed_action.parameters),
                impact_amount=proposed_action.impact_amount,
                impact_currency=proposed_action.impact_currency,
                expected_outcome=proposed_action.expected_outcome,
                observed_outcome=None,
                status=ActionStatus.READY.value,
                execution_blocker=blocker.value if blocker is not None else None,
                execution_eligible=execution_eligible,
                idempotency_key=_hash(
                    {
                        "organization": organization_public_id,
                        "proposed_action": proposed_action.public_id,
                        "review_snapshot": snapshot.snapshot_fingerprint,
                    }
                ),
                authorization_expires_at=decision.decided_at
                + timedelta(hours=ACTION_AUTHORIZATION_HOURS),
                owner_id=owner.id if owner is not None else None,
                owner_public_id=owner.public_id if owner is not None else None,
                owner_name=owner.name if owner is not None else None,
                attempt_count=0,
                version=1,
                created_at=now,
                updated_at=now,
            )
            self._session.add(action)
            self._session.flush()
            self._session.add(
                AuditEventModel(
                    organization_id=review.organization_id,
                    task_id=None,
                    run_id=None,
                    event_type="case.action_authorized",
                    actor_type="member",
                    actor_id=decision.reviewer_public_id,
                    subject_type="action",
                    subject_id=action.public_id,
                    summary="An approved action was added to the controlled queue.",
                    data={
                        "case_id": case.public_id,
                        "review_id": review.public_id,
                        "proposal_id": proposal.public_id,
                        "proposal_version": version.version,
                        "action_type": action.type,
                        "execution_blocker": action.execution_blocker,
                        "authorization_expires_at": (action.authorization_expires_at.isoformat()),
                    },
                    correlation_id=correlation_id,
                    occurred_at=now,
                )
            )
            created.append(action)
        self._session.flush()
        return [self._load_bundle(action) for action in created]

    def import_legacy(
        self,
        *,
        organization_public_id: str,
        command: LegacyActionImport,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        existing_attempt = self._session.scalar(
            select(CaseActionAttemptModel)
            .join(
                CaseActionModel,
                CaseActionModel.id == CaseActionAttemptModel.action_id,
            )
            .join(
                OrganizationModel,
                OrganizationModel.id == CaseActionAttemptModel.organization_id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseActionAttemptModel.legacy_tool_attempt_id == command.legacy_tool_attempt_id,
            )
        )
        if existing_attempt is not None:
            existing_action = self._session.get(
                CaseActionModel,
                existing_attempt.action_id,
            )
            if existing_action is None:
                raise ActionConflict("The imported legacy action lineage is incomplete.")
            return self._queue_item(existing_action, now=utc_now())

        version = self._session.scalar(
            select(CaseProposalVersionModel).where(
                CaseProposalVersionModel.legacy_proposal_version_id
                == command.legacy_proposal_version_id
            )
        )
        if version is None:
            raise ActionNotFound("The legacy proposal must be imported before its action history.")
        organization = self._session.scalar(
            select(OrganizationModel).where(
                OrganizationModel.id == version.organization_id,
                OrganizationModel.public_id == organization_public_id,
            )
        )
        case = self._session.get(CaseModel, version.case_id)
        proposal = self._session.get(CaseProposalModel, version.proposal_id)
        review = self._session.scalar(
            select(CaseReviewModel).where(
                CaseReviewModel.organization_id == version.organization_id,
                CaseReviewModel.case_id == version.case_id,
                CaseReviewModel.proposal_version_id == version.id,
            )
        )
        if organization is None or case is None or proposal is None or review is None:
            raise ActionNotFound(
                "The generic case, proposal, and review history must be imported first."
            )
        snapshot = self._required_review_snapshot(review)
        decision = self._session.scalar(
            select(CaseReviewDecisionModel).where(
                CaseReviewDecisionModel.organization_id == review.organization_id,
                CaseReviewDecisionModel.case_id == review.case_id,
                CaseReviewDecisionModel.review_id == review.id,
                CaseReviewDecisionModel.decision == "approve",
            )
        )
        if decision is None:
            raise ActionConflict("Legacy execution history requires a preserved approval decision.")
        proposed_actions = list(
            self._session.scalars(
                select(CaseProposedActionModel).where(
                    CaseProposedActionModel.organization_id == version.organization_id,
                    CaseProposedActionModel.case_id == version.case_id,
                    CaseProposedActionModel.proposal_version_id == version.id,
                )
            )
        )
        exact = [action for action in proposed_actions if action.type == command.action_type]
        if len(exact) == 1:
            proposed_action = exact[0]
        elif len(proposed_actions) == 1:
            proposed_action = proposed_actions[0]
        else:
            raise ActionConflict(
                "The legacy tool attempt cannot be matched to one proposed action."
            )
        connection = ConnectionRepository(self._session).resolve_for_action(
            organization_id=organization.id,
            organization_public_id=organization.public_id,
            action_type=proposed_action.type,
        )
        action = self._session.scalar(
            select(CaseActionModel)
            .where(
                CaseActionModel.organization_id == organization.id,
                CaseActionModel.case_id == case.id,
                CaseActionModel.proposed_action_id == proposed_action.id,
            )
            .with_for_update()
        )
        if action is None:
            action = CaseActionModel(
                public_id=_stable_public_id(
                    "AC",
                    organization.public_id,
                    proposed_action.public_id,
                    snapshot.snapshot_fingerprint,
                ),
                organization_id=organization.id,
                case_id=case.id,
                proposal_id=proposal.id,
                proposal_version_id=version.id,
                proposed_action_id=proposed_action.id,
                review_id=review.id,
                review_snapshot_id=snapshot.id,
                review_decision_id=decision.id,
                connection_id=connection.id,
                legacy_proposal_version_id=version.legacy_proposal_version_id,
                type=proposed_action.type,
                label=proposed_action.label,
                target=command.target,
                typed_parameters=dict(command.parameters),
                impact_amount=proposed_action.impact_amount,
                impact_currency=proposed_action.impact_currency,
                expected_outcome=proposed_action.expected_outcome,
                observed_outcome=command.observed_outcome,
                status=command.status.value,
                execution_blocker=ActionExecutionBlocker.STALE_PROPOSAL.value,
                execution_eligible=False,
                idempotency_key=command.idempotency_key,
                authorization_expires_at=decision.decided_at
                + timedelta(hours=ACTION_AUTHORIZATION_HOURS),
                owner_id=None,
                owner_public_id=None,
                owner_name=None,
                attempt_count=0,
                version=1,
                created_at=command.started_at,
                updated_at=command.finished_at,
            )
            self._session.add(action)
            self._session.flush()
        attempt_number = action.attempt_count + 1
        attempt = CaseActionAttemptModel(
            public_id=_stable_public_id(
                "AT",
                action.public_id,
                "legacy",
                str(command.legacy_tool_attempt_id),
            ),
            organization_id=action.organization_id,
            case_id=action.case_id,
            action_id=action.id,
            actor_id=None,
            actor_public_id="LEGACY-UNKNOWN",
            actor_name="Legacy actor unavailable",
            actor_role=None,
            legacy_tool_attempt_id=command.legacy_tool_attempt_id,
            number=attempt_number,
            command=ActionAttemptCommand.LEGACY_IMPORT.value,
            outcome=command.attempt_outcome.value,
            side_effect_state=command.side_effect_state.value,
            detail=command.observed_outcome,
            error_code=command.error_code,
            request_fingerprint=command.request_fingerprint,
            response_fingerprint=command.response_fingerprint,
            started_at=command.started_at,
            finished_at=command.finished_at,
        )
        self._session.add(attempt)
        self._session.flush()
        if command.receipt is not None:
            existing_receipt = self._receipt(action)
            if existing_receipt is None:
                self._session.add(
                    CaseActionReceiptModel(
                        public_id=_stable_public_id(
                            "AR",
                            action.public_id,
                            command.receipt.external_reference,
                        ),
                        organization_id=action.organization_id,
                        case_id=action.case_id,
                        action_id=action.id,
                        attempt_id=attempt.id,
                        legacy_external_receipt_id=(command.receipt.legacy_external_receipt_id),
                        provider=command.receipt.provider,
                        external_reference=command.receipt.external_reference,
                        idempotency_key=command.idempotency_key,
                        status=command.receipt.status,
                        data_fingerprint=command.receipt.data_fingerprint,
                        recorded_at=command.receipt.recorded_at,
                    )
                )
        action.attempt_count = attempt_number
        action.execution_eligible = False
        action.execution_blocker = ActionExecutionBlocker.STALE_PROPOSAL.value
        action.observed_outcome = command.observed_outcome
        if self._receipt(action) is not None or command.receipt is not None:
            action.status = ActionStatus.COMPLETED.value
        elif (
            action.status == ActionStatus.OUTCOME_UNKNOWN.value
            or command.status is ActionStatus.OUTCOME_UNKNOWN
        ):
            action.status = ActionStatus.OUTCOME_UNKNOWN.value
        else:
            action.status = ActionStatus.FAILED_SAFE.value
        action.version += 1
        action.updated_at = max(action.updated_at, command.finished_at)
        self._add_audit(
            action=action,
            event_type="case.action_legacy_imported",
            actor_type="system",
            actor_id="legacy-action-backfill",
            summary="Historical action evidence was imported without replay.",
            data={
                "legacy_tool_attempt_id": str(command.legacy_tool_attempt_id),
                "source_tool_name": command.source_tool_name,
                "attempt_id": attempt.public_id,
                "status": action.status,
                "execution_eligible": False,
            },
            correlation_id=correlation_id,
            occurred_at=command.finished_at,
        )
        self._session.flush()
        return self._queue_item(action, now=utc_now())
