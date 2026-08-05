from dataclasses import dataclass

from app.domain.cases import (
    CASE_TRANSITIONS,
    CaseCommand,
    CaseStatus,
    CaseWorkspaceRecord,
)
from app.domain.decision_briefs import DecisionBriefRecord, DecisionProposalState
from app.domain.identity import ActorContext, Permission
from app.domain.policies import EvidenceRetrievalStatus, PolicyEvidenceBundle
from app.persistence.case_repository import CaseRepository
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.policy_repository import PolicyRepository
from app.persistence.review_repository import ReviewRepository
from app.services.case_service import CaseService


@dataclass(frozen=True, slots=True)
class CaseWorkspaceProjection:
    workspace: CaseWorkspaceRecord
    brief: DecisionBriefRecord | None
    evidence: tuple[PolicyEvidenceBundle, ...]
    available_commands: tuple[CaseCommand, ...]


class CaseWorkspaceQueryService:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        decisions: DecisionBriefRepository,
        policies: PolicyRepository,
        reviews: ReviewRepository,
    ) -> None:
        self._case_service = CaseService(cases)
        self._decisions = decisions
        self._policies = policies
        self._reviews = reviews

    def get(self, *, actor: ActorContext, case_id: str) -> CaseWorkspaceProjection:
        workspace = self._case_service.get_case(actor=actor, case_id=case_id)
        return self.project(actor=actor, workspace=workspace)

    def project(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
    ) -> CaseWorkspaceProjection:
        brief = self._decisions.get_latest(
            organization_public_id=actor.organization_id,
            case_public_id=workspace.case.public_id,
        )
        evidence = self._policies.list_evidence_for_case(
            organization_public_id=actor.organization_id,
            case_public_id=workspace.case.public_id,
        )
        if brief is not None:
            bound_ids = set(brief.version.evidence_ids)
            evidence = [item for item in evidence if item.evidence.public_id in bound_ids]

        return CaseWorkspaceProjection(
            workspace=workspace,
            brief=brief,
            evidence=tuple(evidence),
            available_commands=tuple(
                self._available_commands(
                    actor=actor,
                    workspace=workspace,
                    brief=brief,
                )
            ),
        )

    def _available_commands(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
        brief: DecisionBriefRecord | None,
    ) -> list[CaseCommand]:
        commands: list[CaseCommand] = []
        if actor.can(Permission.CASE_MANAGE):
            if workspace.owner is None:
                commands.append("assign_to_me")
            commands.extend(["send_reply", "add_note"])
            if CaseStatus.INFORMATION_NEEDED in CASE_TRANSITIONS[workspace.case.status]:
                commands.append("request_information")
            if (
                workspace.case.status
                in {
                    CaseStatus.INFORMATION_NEEDED,
                    CaseStatus.WAITING_CUSTOMER,
                }
                and CaseStatus.INVESTIGATING in CASE_TRANSITIONS[workspace.case.status]
            ):
                commands.append("resume_investigation")
            if workspace.case.status is not CaseStatus.COMPLETED:
                commands.append("revise_resolution")
            commands.append("save_draft")
            if self._can_submit_or_escalate(
                actor=actor,
                workspace=workspace,
                brief=brief,
            ):
                assert brief is not None
                if (
                    brief.version.state is DecisionProposalState.READY_FOR_REVIEW
                    and brief.run.policy_status is EvidenceRetrievalStatus.RELEVANT
                    and any(action.review_required for action in brief.proposed_actions)
                ):
                    commands.append("submit_for_review")
                elif (
                    brief.version.state is DecisionProposalState.INFORMATION_NEEDED
                    and brief.run.policy_status is not EvidenceRetrievalStatus.RELEVANT
                ):
                    commands.append("escalate")
        if actor.can(Permission.AUDIT_READ):
            commands.append("export_audit")
        return commands

    def _can_submit_or_escalate(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
        brief: DecisionBriefRecord | None,
    ) -> bool:
        if brief is None:
            return False
        if workspace.case.status not in {
            CaseStatus.INVESTIGATING,
            CaseStatus.IN_PROGRESS,
        }:
            return False
        if brief.proposal.current_version != brief.version.version:
            return False
        return (
            self._reviews.get_for_proposal(
                organization_public_id=actor.organization_id,
                case_public_id=workspace.case.public_id,
                proposal_version=brief.version.version,
            )
            is None
        )
