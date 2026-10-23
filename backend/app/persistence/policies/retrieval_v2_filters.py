from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.domain.policies import PolicyVersionStatus
from app.persistence.models import (
    GovernedPolicyClauseEmbeddingV2Model,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    PolicyModel,
)

from ._base import _json_dimension_match


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    base: tuple[ColumnElement[bool], ...]
    category: ColumnElement[bool]
    applicable: ColumnElement[bool]
    active_match: ColumnElement[bool]

    @property
    def active(self) -> tuple[ColumnElement[bool], ...]:
        return (*self.base, self.active_match)


def build_retrieval_filters(
    *,
    organization_id: UUID,
    case_category: str,
    products: set[str],
    region: str,
    channel: str,
    customer_tier: str,
    as_of: datetime,
) -> RetrievalFilters:
    version = GovernedPolicyVersionModel
    base = (
        version.organization_id == organization_id,
        version.status.in_(
            [
                PolicyVersionStatus.PUBLISHED.value,
                PolicyVersionStatus.SCHEDULED.value,
            ]
        ),
        version.immutable.is_(True),
    )
    category = _json_dimension_match(version.case_categories, {case_category})
    context = and_(
        category,
        _json_dimension_match(version.products, products),
        _json_dimension_match(version.regions, {region}),
        _json_dimension_match(version.channels, {channel}),
        _json_dimension_match(version.customer_tiers, {customer_tier}),
    )
    effective = and_(
        or_(version.effective_from.is_(None), version.effective_from <= as_of),
        or_(version.effective_to.is_(None), version.effective_to > as_of),
    )
    return RetrievalFilters(
        base=base,
        category=category,
        applicable=context,
        active_match=and_(context, effective),
    )


def retrieval_counts(
    session: Session,
    filters: RetrievalFilters,
) -> tuple[int, int, int]:
    version = GovernedPolicyVersionModel
    row = session.execute(
        select(
            func.count(distinct(version.policy_id)).filter(filters.category),
            func.count(distinct(version.policy_id)).filter(filters.applicable),
            func.count(distinct(version.policy_id)).filter(filters.active_match),
        ).where(*filters.base)
    ).one()
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)


def conflicting_scopes(
    session: Session,
    filters: RetrievalFilters,
) -> tuple[str, ...]:
    version = GovernedPolicyVersionModel
    return tuple(
        session.scalars(
            select(version.decision_scope)
            .where(*filters.active)
            .group_by(version.decision_scope)
            .having(func.count(distinct(version.policy_id)) > 1)
            .order_by(version.decision_scope)
        )
    )


def active_index_is_complete(
    session: Session,
    filters: RetrievalFilters,
    profile_id: UUID,
) -> bool:
    clause = GovernedPolicyClauseModel
    embedding = GovernedPolicyClauseEmbeddingV2Model
    base = (
        select(func.count(clause.id))
        .select_from(PolicyModel)
        .join(
            GovernedPolicyVersionModel,
            and_(
                GovernedPolicyVersionModel.organization_id
                == PolicyModel.organization_id,
                GovernedPolicyVersionModel.policy_id == PolicyModel.id,
            ),
        )
        .join(
            clause,
            and_(
                clause.organization_id == GovernedPolicyVersionModel.organization_id,
                clause.policy_id == GovernedPolicyVersionModel.policy_id,
                clause.policy_version_id == GovernedPolicyVersionModel.id,
            ),
        )
        .where(*filters.active)
    )
    total = session.scalar(base) or 0
    indexed = session.scalar(
        base.join(
            embedding,
            and_(
                embedding.organization_id == clause.organization_id,
                embedding.clause_id == clause.id,
                embedding.profile_id == profile_id,
                embedding.source_content_hash == clause.content_hash,
            ),
        )
    ) or 0
    return total > 0 and total == indexed
