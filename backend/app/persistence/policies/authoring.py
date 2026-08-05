from uuid import uuid4

from sqlalchemy import func, select

from app.domain.policies import (
    IndexedPolicyClause,
    PolicyAlreadyExists,
    PolicyCreate,
    PolicyDraftContent,
    PolicyLifecycleStatus,
    PolicyNotFound,
    PolicyWorkspaceRecord,
)
from app.persistence.models import (
    GovernedPolicyVersionModel,
    PolicyModel,
)

from ._base import (
    PolicyRepositoryBase,
)


class PolicyAuthoringRepository(PolicyRepositoryBase):
    def create_policy(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        actor_type: str,
        command: PolicyCreate,
        clauses: list[IndexedPolicyClause],
        source_error: str | None,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise PolicyNotFound("The actor organization was not found.")
        owner = self._required_member(organization_id, actor_id)
        existing = self._session.scalar(
            select(PolicyModel.id).where(
                PolicyModel.organization_id == organization_id,
                PolicyModel.public_id == command.public_id,
            )
        )
        if existing is not None:
            raise PolicyAlreadyExists(f"Policy {command.public_id} already exists.")

        policy_uuid = uuid4()
        status = (
            PolicyLifecycleStatus.DRAFT
            if command.content is not None
            else PolicyLifecycleStatus.PARSING_FAILED
        )
        policy = PolicyModel(
            id=policy_uuid,
            public_id=command.public_id,
            organization_id=organization_id,
            title=command.title,
            description=command.description,
            status=status.value,
            owner_id=owner.id,
            source_kind=command.source_kind.value,
            source_name=command.source_name,
            source_error=source_error,
            current_version=1 if command.content is not None else 0,
            version=1,
        )
        self._session.add(policy)
        self._session.flush()
        if command.content is not None:
            self._add_version(
                policy=policy,
                version_number=1,
                actor_id=actor_id,
                content=command.content,
                clauses=clauses,
                legacy_policy_version_id=None,
            )
        self._audit(
            policy=policy,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type=("policy.created" if command.content is not None else "policy.parse_failed"),
            summary=(
                "Policy draft created."
                if command.content is not None
                else "Policy source could not be parsed."
            ),
            data={"source_kind": command.source_kind.value},
            correlation_id=correlation_id,
        )
        self._session.flush()
        return self._required_workspace(organization_public_id, command.public_id)

    def create_draft(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        content: PolicyDraftContent,
        clauses: list[IndexedPolicyClause],
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        policy = self._required_policy(organization_public_id, policy_public_id)
        latest_version = self._session.scalar(
            select(func.max(GovernedPolicyVersionModel.version)).where(
                GovernedPolicyVersionModel.organization_id == policy.organization_id,
                GovernedPolicyVersionModel.policy_id == policy.id,
            )
        )
        next_version = (latest_version or 0) + 1
        updated = self._update_policy(
            policy=policy,
            expected_version=expected_policy_version,
            values={
                "status": PolicyLifecycleStatus.DRAFT.value,
                "current_version": next_version,
                "source_error": None,
            },
        )
        self._add_version(
            policy=updated,
            version_number=next_version,
            actor_id=actor_id,
            content=content,
            clauses=clauses,
            legacy_policy_version_id=None,
        )
        self._audit(
            policy=updated,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="policy.draft_created",
            summary=f"Policy version {next_version} draft created.",
            data={"policy_version": next_version},
            correlation_id=correlation_id,
        )
        self._session.flush()
        return self._required_workspace(organization_public_id, policy_public_id)

    def retry_source(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        content: PolicyDraftContent,
        clauses: list[IndexedPolicyClause],
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        policy = self._required_policy(organization_public_id, policy_public_id)
        updated = self._update_policy(
            policy=policy,
            expected_version=expected_policy_version,
            values={
                "status": PolicyLifecycleStatus.DRAFT.value,
                "current_version": 1,
                "source_error": None,
            },
        )
        self._add_version(
            policy=updated,
            version_number=1,
            actor_id=actor_id,
            content=content,
            clauses=clauses,
            legacy_policy_version_id=None,
        )
        self._audit(
            policy=updated,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="policy.source_recovered",
            summary="Policy source parsed and draft version 1 created.",
            data={"policy_version": 1},
            correlation_id=correlation_id,
        )
        self._session.flush()
        return self._required_workspace(organization_public_id, policy_public_id)
