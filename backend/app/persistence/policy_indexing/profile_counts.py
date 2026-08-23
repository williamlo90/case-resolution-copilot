from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.persistence.models import (
    GovernedPolicyClauseEmbeddingV2Model,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    PolicyEmbeddingProfileModel,
    utc_now,
)

_ACTIVE_VERSION_STATES = ("published", "scheduled")


def refresh_profile_counts(
    session: Session,
    profile: PolicyEmbeddingProfileModel,
) -> None:
    clause = GovernedPolicyClauseModel
    version = GovernedPolicyVersionModel
    embedding = GovernedPolicyClauseEmbeddingV2Model
    version_filters = (
        version.status.in_(_ACTIVE_VERSION_STATES),
        version.immutable.is_(True),
    )
    expected = session.scalar(
        select(func.count(clause.id))
        .select_from(version)
        .join(
            clause,
            and_(
                clause.organization_id == version.organization_id,
                clause.policy_id == version.policy_id,
                clause.policy_version_id == version.id,
            ),
        )
        .where(*version_filters)
    ) or 0
    indexed = session.scalar(
        select(func.count(embedding.id))
        .select_from(version)
        .join(
            clause,
            and_(
                clause.organization_id == version.organization_id,
                clause.policy_id == version.policy_id,
                clause.policy_version_id == version.id,
            ),
        )
        .join(
            embedding,
            and_(
                embedding.organization_id == clause.organization_id,
                embedding.clause_id == clause.id,
                embedding.profile_id == profile.id,
                embedding.source_content_hash == clause.content_hash,
            ),
        )
        .where(*version_filters)
    ) or 0
    profile.expected_clause_count = expected
    profile.indexed_clause_count = indexed
    if expected > 0 and indexed == expected:
        if profile.status not in {"active", "retired"}:
            if profile.status != "ready":
                profile.ready_at = utc_now()
            profile.status = "ready"
    elif profile.status not in {"retired", "failed"}:
        profile.status = "building"
        profile.ready_at = None
