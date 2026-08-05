from uuid import uuid4

from sqlalchemy import and_, select

from app.domain.policies import (
    LegacyPolicyImport,
    PolicyLifecycleStatus,
    PolicyNotFound,
    PolicyVersionStatus,
    PolicyWorkspaceRecord,
)
from app.persistence.models import (
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    PolicyModel,
    utc_now,
)

from ._base import (
    PolicyRepositoryBase,
    _stable_public_id,
)


class LegacyPolicyRepository(PolicyRepositoryBase):
    def import_legacy_policy(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        actor_type: str,
        command: LegacyPolicyImport,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise PolicyNotFound("The target organization was not found.")
        owner = self._required_member(organization_id, actor_id)
        linked_policy_id = self._session.scalar(
            select(PolicyModel.public_id)
            .join(
                GovernedPolicyVersionModel,
                and_(
                    GovernedPolicyVersionModel.organization_id == PolicyModel.organization_id,
                    GovernedPolicyVersionModel.policy_id == PolicyModel.id,
                ),
            )
            .where(
                PolicyModel.organization_id == organization_id,
                GovernedPolicyVersionModel.legacy_policy_version_id
                == command.legacy_policy_version_id,
            )
        )
        if linked_policy_id is not None:
            return self._required_workspace(organization_public_id, linked_policy_id)

        policy = self._session.scalar(
            select(PolicyModel).where(
                PolicyModel.organization_id == organization_id,
                PolicyModel.public_id == command.public_id,
            )
        )
        if policy is None:
            policy = PolicyModel(
                id=uuid4(),
                public_id=command.public_id,
                organization_id=organization_id,
                title=command.title,
                description=command.description,
                status=(
                    PolicyLifecycleStatus.PUBLISHED.value
                    if command.status is PolicyVersionStatus.PUBLISHED
                    else PolicyLifecycleStatus.RETIRED.value
                ),
                owner_id=owner.id,
                source_kind="manual",
                source_name=f"Legacy policy {command.source_id}",
                source_error=None,
                current_version=command.version,
                version=1,
                created_at=command.created_at,
                updated_at=command.created_at,
            )
            self._session.add(policy)
        else:
            if policy.current_version < command.version:
                policy.current_version = command.version
                policy.title = command.title
                policy.status = (
                    PolicyLifecycleStatus.PUBLISHED.value
                    if command.status is PolicyVersionStatus.PUBLISHED
                    else PolicyLifecycleStatus.RETIRED.value
                )
            policy.version += 1
            policy.updated_at = utc_now()

        self._session.flush()
        version_uuid = uuid4()
        version = GovernedPolicyVersionModel(
            id=version_uuid,
            public_id=_stable_public_id("POLV", command.public_id, str(command.version)),
            organization_id=organization_id,
            policy_id=policy.id,
            legacy_policy_version_id=command.legacy_policy_version_id,
            version=command.version,
            record_version=1,
            status=command.status.value,
            immutable=True,
            source_text=command.source_text,
            content_hash=command.content_hash,
            decision_scope=command.applicability.decision_scope,
            case_categories=command.applicability.case_categories,
            products=command.applicability.products,
            regions=command.applicability.regions,
            channels=command.applicability.channels,
            customer_tiers=command.applicability.customer_tiers,
            effective_from=command.effective_from,
            effective_to=command.effective_to,
            created_by=actor_id,
            created_at=command.created_at,
            submitted_at=command.created_at,
            published_at=(
                command.created_at if command.status is PolicyVersionStatus.PUBLISHED else None
            ),
            retired_at=(
                command.created_at if command.status is PolicyVersionStatus.RETIRED else None
            ),
        )
        clause_models = [
            GovernedPolicyClauseModel(
                public_id=clause.public_id,
                organization_id=organization_id,
                policy_id=policy.id,
                policy_version_id=version_uuid,
                sequence=clause.sequence,
                heading=clause.heading,
                text=clause.text,
                applies_when=clause.applies_when,
                content_hash=clause.content_hash,
                chunking_version=clause.chunking_version,
                embedding_version=clause.embedding_version,
                index_version=clause.index_version,
                embedding=clause.embedding,
            )
            for clause in command.clauses
        ]
        self._session.add(version)
        self._session.flush()
        self._session.add_all(clause_models)
        self._audit(
            policy=policy,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="policy.legacy_imported",
            summary=f"Legacy policy version {command.version} imported.",
            data={
                "source_id": command.source_id,
                "legacy_policy_version_id": str(command.legacy_policy_version_id),
            },
            correlation_id=correlation_id,
        )
        self._session.flush()
        return self._required_workspace(organization_public_id, command.public_id)
