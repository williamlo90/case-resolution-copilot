from datetime import datetime

from sqlalchemy import or_, select

from app.domain.policies import (
    PolicyLifecycleStatus,
    PolicyVersionStatus,
    PolicyWorkspaceRecord,
)
from app.persistence.models import (
    GovernedPolicyVersionModel,
    utc_now,
)

from ._base import (
    PolicyRepositoryBase,
)


class PolicyLifecycleRepository(PolicyRepositoryBase):
    def submit_review(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        version_number: int,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        expected_version: int,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        policy = self._required_policy(organization_public_id, policy_public_id)
        version = self._required_version(policy, version_number)
        now = utc_now()
        updated_policy = self._update_policy(
            policy=policy,
            expected_version=expected_policy_version,
            values={"status": PolicyLifecycleStatus.IN_REVIEW.value},
        )
        self._update_version(
            version=version,
            expected_version=expected_version,
            values={
                "status": PolicyVersionStatus.IN_REVIEW.value,
                "submitted_at": now,
            },
        )
        self._audit(
            policy=updated_policy,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="policy.review_submitted",
            summary=f"Policy version {version_number} submitted for review.",
            data={"policy_version": version_number},
            correlation_id=correlation_id,
        )
        return self._required_workspace(organization_public_id, policy_public_id)

    def mark_conflicting(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        version_number: int,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        expected_version: int,
        conflicting_policy_ids: list[str],
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        policy = self._required_policy(organization_public_id, policy_public_id)
        version = self._required_version(policy, version_number)
        updated = self._update_policy(
            policy=policy,
            expected_version=expected_policy_version,
            values={"status": PolicyLifecycleStatus.CONFLICTING.value},
        )
        self._update_version(version=version, expected_version=expected_version, values={})
        self._audit(
            policy=updated,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="policy.conflict_detected",
            summary="Policy publication blocked by overlapping authority.",
            data={"conflicting_policy_ids": conflicting_policy_ids},
            correlation_id=correlation_id,
        )
        return self._required_workspace(organization_public_id, policy_public_id)

    def activate_version(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        version_number: int,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        expected_version: int,
        target: PolicyVersionStatus,
        effective_from: datetime,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        policy = self._required_policy(organization_public_id, policy_public_id)
        version = self._required_version(policy, version_number)
        now = utc_now()
        if target is PolicyVersionStatus.PUBLISHED:
            previous_versions = self._session.scalars(
                select(GovernedPolicyVersionModel).where(
                    GovernedPolicyVersionModel.organization_id == policy.organization_id,
                    GovernedPolicyVersionModel.policy_id == policy.id,
                    GovernedPolicyVersionModel.id != version.id,
                    GovernedPolicyVersionModel.status.in_(
                        [
                            PolicyVersionStatus.PUBLISHED.value,
                            PolicyVersionStatus.SCHEDULED.value,
                        ]
                    ),
                )
            )
            for previous in previous_versions:
                previous.status = PolicyVersionStatus.RETIRED.value
                previous.record_version += 1
                previous.retired_at = now
                if previous.effective_to is None or previous.effective_to > effective_from:
                    previous.effective_to = effective_from

        updated_policy = self._update_policy(
            policy=policy,
            expected_version=expected_policy_version,
            values={"status": target.value},
        )
        self._update_version(
            version=version,
            expected_version=expected_version,
            values={
                "status": target.value,
                "immutable": True,
                "effective_from": effective_from,
                "published_at": now,
            },
        )
        event = (
            "policy.published" if target is PolicyVersionStatus.PUBLISHED else "policy.scheduled"
        )
        self._audit(
            policy=updated_policy,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type=event,
            summary=f"Policy version {version_number} {target.value}.",
            data={
                "policy_version": version_number,
                "effective_from": effective_from.isoformat(),
            },
            correlation_id=correlation_id,
        )
        return self._required_workspace(organization_public_id, policy_public_id)

    def retire_version(
        self,
        *,
        organization_public_id: str,
        policy_public_id: str,
        version_number: int,
        actor_id: str,
        actor_type: str,
        expected_policy_version: int,
        expected_version: int,
        correlation_id: str,
    ) -> PolicyWorkspaceRecord:
        policy = self._required_policy(organization_public_id, policy_public_id)
        version = self._required_version(policy, version_number)
        now = utc_now()
        previous_active = None
        if version.status == PolicyVersionStatus.SCHEDULED.value:
            previous_active = self._session.scalar(
                select(GovernedPolicyVersionModel)
                .where(
                    GovernedPolicyVersionModel.organization_id == policy.organization_id,
                    GovernedPolicyVersionModel.policy_id == policy.id,
                    GovernedPolicyVersionModel.id != version.id,
                    GovernedPolicyVersionModel.status == PolicyVersionStatus.PUBLISHED.value,
                    GovernedPolicyVersionModel.immutable.is_(True),
                    or_(
                        GovernedPolicyVersionModel.effective_from.is_(None),
                        GovernedPolicyVersionModel.effective_from <= now,
                    ),
                    or_(
                        GovernedPolicyVersionModel.effective_to.is_(None),
                        GovernedPolicyVersionModel.effective_to > now,
                    ),
                )
                .order_by(GovernedPolicyVersionModel.version.desc())
            )
        policy_values: dict[str, object] = {"status": PolicyLifecycleStatus.RETIRED.value}
        if previous_active is not None:
            policy_values = {
                "status": PolicyLifecycleStatus.PUBLISHED.value,
                "current_version": previous_active.version,
            }
        updated_policy = self._update_policy(
            policy=policy,
            expected_version=expected_policy_version,
            values=policy_values,
        )
        values: dict[str, object] = {
            "status": PolicyVersionStatus.RETIRED.value,
            "retired_at": now,
        }
        if (version.effective_from is None or version.effective_from < now) and (
            version.effective_to is None or version.effective_to > now
        ):
            values["effective_to"] = now
        self._update_version(
            version=version,
            expected_version=expected_version,
            values=values,
        )
        self._audit(
            policy=updated_policy,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="policy.retired",
            summary=f"Policy version {version_number} retired.",
            data={
                "policy_version": version_number,
                "restored_policy_version": (
                    previous_active.version if previous_active is not None else None
                ),
            },
            correlation_id=correlation_id,
        )
        return self._required_workspace(organization_public_id, policy_public_id)
