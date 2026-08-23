from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from app.domain.policies import (
    GovernedPolicyClauseRecord,
    GovernedPolicyVersionRecord,
    PolicyCandidateRecord,
    PolicyNotFound,
    PolicyRecord,
)
from app.domain.retrieval_v2 import HybridPolicyCandidatePage
from app.persistence.models import (
    GovernedPolicyClauseEmbeddingV2Model,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    PolicyEmbeddingProfileModel,
    PolicyModel,
)

from ._base import PolicyRepositoryBase
from .retrieval_v2_filters import (
    RetrievalFilters,
    active_index_is_complete,
    build_retrieval_filters,
    conflicting_scopes,
    retrieval_counts,
)
from .retrieval_v2_query import lexical_websearch_query

DENSE_MAX_COSINE_DISTANCE = 0.55
LEXICAL_MIN_RANK = 0.05


class PolicyRetrievalV2Repository(PolicyRepositoryBase):
    def inspect_hybrid_scope(
        self,
        *,
        organization_public_id: str,
        profile_key: str,
        case_category: str,
        products: set[str],
        region: str,
        channel: str,
        customer_tier: str,
        as_of: datetime,
    ) -> HybridPolicyCandidatePage:
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise PolicyNotFound("The actor organization was not found.")
        filters = build_retrieval_filters(
            organization_id=organization_id,
            case_category=case_category,
            products=products,
            region=region,
            channel=channel,
            customer_tier=customer_tier,
            as_of=as_of,
        )
        counts = retrieval_counts(self._session, filters)
        conflicts = conflicting_scopes(self._session, filters)
        if counts[2] == 0 or conflicts:
            return _page(profile_key, counts, conflicts=conflicts)
        profile = self._available_profile(profile_key)
        ready = profile is not None and active_index_is_complete(
            self._session,
            filters,
            profile.id,
        )
        return _page(profile_key, counts, index_ready=ready)

    def search_hybrid_candidates(
        self,
        *,
        organization_public_id: str,
        profile_key: str,
        case_category: str,
        products: set[str],
        region: str,
        channel: str,
        customer_tier: str,
        as_of: datetime,
        query_text: str,
        query_embedding: list[float],
        candidate_limit: int,
    ) -> HybridPolicyCandidatePage:
        if candidate_limit < 1 or candidate_limit > 64:
            raise ValueError("candidate_limit must be between 1 and 64")
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise PolicyNotFound("The actor organization was not found.")
        filters = build_retrieval_filters(
            organization_id=organization_id,
            case_category=case_category,
            products=products,
            region=region,
            channel=channel,
            customer_tier=customer_tier,
            as_of=as_of,
        )
        counts = retrieval_counts(self._session, filters)
        conflicts = conflicting_scopes(self._session, filters)
        if counts[2] == 0 or conflicts:
            return _page(profile_key, counts, conflicts=conflicts)

        profile = self._available_profile(profile_key)
        if profile is None or not active_index_is_complete(
            self._session,
            filters,
            profile.id,
        ):
            return _page(profile_key, counts)
        return _page(
            profile_key,
            counts,
            index_ready=True,
            dense=self._dense(filters, profile.id, query_embedding, candidate_limit),
            lexical=self._lexical(filters, profile.id, query_text, candidate_limit),
        )

    def _available_profile(
        self,
        profile_key: str,
    ) -> PolicyEmbeddingProfileModel | None:
        return self._session.scalar(
            select(PolicyEmbeddingProfileModel).where(
                PolicyEmbeddingProfileModel.profile_key == profile_key,
                PolicyEmbeddingProfileModel.status.in_(["building", "ready", "active"]),
            )
        )

    def _dense(
        self,
        filters: RetrievalFilters,
        profile_id: UUID,
        query_embedding: list[float],
        limit: int,
    ) -> tuple[PolicyCandidateRecord, ...]:
        distance = GovernedPolicyClauseEmbeddingV2Model.embedding.cosine_distance(
            query_embedding
        )
        statement = (
            _ranked_rows(filters.active, profile_id)
            .where(distance <= DENSE_MAX_COSINE_DISTANCE)
            .add_columns(distance)
            .order_by(
                distance,
                PolicyModel.public_id,
                GovernedPolicyVersionModel.version.desc(),
                GovernedPolicyClauseModel.sequence,
            )
            .limit(limit)
        )
        return _candidates(self._session.execute(statement).all())

    def _lexical(
        self,
        filters: RetrievalFilters,
        profile_id: UUID,
        query_text: str,
        limit: int,
    ) -> tuple[PolicyCandidateRecord, ...]:
        query = func.websearch_to_tsquery("simple", lexical_websearch_query(query_text))
        rank = func.ts_rank_cd(GovernedPolicyClauseModel.search_vector, query)
        statement = (
            _ranked_rows(filters.active, profile_id)
            .where(
                GovernedPolicyClauseModel.search_vector.op("@@")(query),
                rank > LEXICAL_MIN_RANK,
            )
            .add_columns(rank)
            .order_by(
                rank.desc(),
                PolicyModel.public_id,
                GovernedPolicyVersionModel.version.desc(),
                GovernedPolicyClauseModel.sequence,
            )
            .limit(limit)
        )
        return _candidates(self._session.execute(statement).all())


def _ranked_rows(
    active_filters: Sequence[ColumnElement[bool]],
    profile_id: UUID,
) -> Select[tuple[PolicyModel, GovernedPolicyVersionModel, GovernedPolicyClauseModel]]:
    version = GovernedPolicyVersionModel
    clause = GovernedPolicyClauseModel
    embedding = GovernedPolicyClauseEmbeddingV2Model
    return (
        select(PolicyModel, version, clause)
        .join(
            version,
            and_(
                version.organization_id == PolicyModel.organization_id,
                version.policy_id == PolicyModel.id,
            ),
        )
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
                embedding.profile_id == profile_id,
                embedding.source_content_hash == clause.content_hash,
            ),
        )
        .where(*active_filters)
    )


def _candidates(rows: Sequence[Sequence[object]]) -> tuple[PolicyCandidateRecord, ...]:
    return tuple(
        PolicyCandidateRecord(
            policy=PolicyRecord.model_validate(row[0]),
            version=GovernedPolicyVersionRecord.model_validate(row[1]),
            clauses=[GovernedPolicyClauseRecord.model_validate(row[2])],
        )
        for row in rows
    )


def _page(
    profile_key: str,
    counts: tuple[int, int, int],
    *,
    conflicts: tuple[str, ...] = (),
    index_ready: bool = False,
    dense: tuple[PolicyCandidateRecord, ...] = (),
    lexical: tuple[PolicyCandidateRecord, ...] = (),
) -> HybridPolicyCandidatePage:
    return HybridPolicyCandidatePage(
        profile_key=profile_key,
        index_ready=index_ready,
        category_matches=counts[0],
        applicable_matches=counts[1],
        active_matches=counts[2],
        conflicting_scopes=conflicts,
        dense=dense,
        lexical=lexical,
    )
