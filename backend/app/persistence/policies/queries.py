from datetime import datetime

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.orm import aliased

from app.domain.policies import (
    CasePolicyEvidenceRecord,
    GovernedPolicyClauseRecord,
    GovernedPolicyVersionRecord,
    PolicyCandidateRecord,
    PolicyEvidenceBundle,
    PolicyLifecycleStatus,
    PolicyListItemRecord,
    PolicyListPageRecord,
    PolicyNotFound,
    PolicyRecord,
    PolicyRetrievalCandidatePage,
    PolicyVersionStatus,
    RankedPolicyCandidateRecord,
)
from app.persistence.models import (
    CaseModel,
    CasePolicyEvidenceModel,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    MembershipModel,
    OrganizationModel,
    PolicyModel,
)

from ._base import (
    PolicyRepositoryBase,
    _json_dimension_match,
)


class PolicyQueryRepository(PolicyRepositoryBase):
    def list_policies(
        self,
        *,
        organization_public_id: str,
        status: PolicyLifecycleStatus | None,
        query: str | None,
        offset: int,
        limit: int,
    ) -> PolicyListPageRecord:
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise PolicyNotFound("The actor organization was not found.")
        owner = aliased(MembershipModel)
        current_version = aliased(GovernedPolicyVersionModel)
        usage = (
            select(
                CasePolicyEvidenceModel.policy_id.label("policy_id"),
                func.count(distinct(CasePolicyEvidenceModel.case_id)).label("used_by_cases"),
            )
            .where(CasePolicyEvidenceModel.organization_id == organization_id)
            .group_by(CasePolicyEvidenceModel.policy_id)
            .subquery()
        )
        filters = [PolicyModel.organization_id == organization_id]
        if status is not None:
            filters.append(PolicyModel.status == status.value)
        if query:
            escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            term = f"%{escaped}%"
            filters.append(
                or_(
                    PolicyModel.public_id.ilike(term, escape="\\"),
                    PolicyModel.title.ilike(term, escape="\\"),
                    PolicyModel.description.ilike(term, escape="\\"),
                )
            )
        total = self._session.scalar(select(func.count(PolicyModel.id)).where(*filters)) or 0
        rows = self._session.execute(
            select(
                PolicyModel,
                owner,
                current_version,
                func.coalesce(usage.c.used_by_cases, 0),
            )
            .join(
                owner,
                and_(
                    owner.organization_id == PolicyModel.organization_id,
                    owner.id == PolicyModel.owner_id,
                ),
            )
            .outerjoin(usage, usage.c.policy_id == PolicyModel.id)
            .outerjoin(
                current_version,
                and_(
                    current_version.organization_id == PolicyModel.organization_id,
                    current_version.policy_id == PolicyModel.id,
                    current_version.version == PolicyModel.current_version,
                ),
            )
            .where(*filters)
            .order_by(PolicyModel.updated_at.desc(), PolicyModel.public_id)
            .offset(offset)
            .limit(limit)
        ).all()
        items = [
            PolicyListItemRecord(
                policy=PolicyRecord.model_validate(policy),
                owner=self._owner_record(member),
                current_version=(
                    GovernedPolicyVersionRecord.model_validate(version) if version else None
                ),
                used_by_cases=int(used_by_cases),
            )
            for policy, member, version, used_by_cases in rows
        ]
        next_offset = offset + len(items) if offset + len(items) < total else None
        return PolicyListPageRecord(items=items, next_offset=next_offset, total=total)

    def list_candidates(self, *, organization_public_id: str) -> list[PolicyCandidateRecord]:
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise PolicyNotFound("The actor organization was not found.")
        rows = self._session.execute(
            select(PolicyModel, GovernedPolicyVersionModel)
            .join(
                GovernedPolicyVersionModel,
                and_(
                    GovernedPolicyVersionModel.organization_id == PolicyModel.organization_id,
                    GovernedPolicyVersionModel.policy_id == PolicyModel.id,
                ),
            )
            .where(
                PolicyModel.organization_id == organization_id,
                GovernedPolicyVersionModel.status.in_(
                    [
                        PolicyVersionStatus.PUBLISHED.value,
                        PolicyVersionStatus.SCHEDULED.value,
                    ]
                ),
                GovernedPolicyVersionModel.immutable.is_(True),
            )
        ).all()
        candidates = []
        for policy, version in rows:
            clauses = self._clause_records(policy, version)
            candidates.append(
                PolicyCandidateRecord(
                    policy=PolicyRecord.model_validate(policy),
                    version=GovernedPolicyVersionRecord.model_validate(version),
                    clauses=clauses,
                )
            )
        return candidates

    def search_retrieval_candidates(
        self,
        *,
        organization_public_id: str,
        case_category: str,
        products: set[str],
        region: str,
        channel: str,
        customer_tier: str,
        as_of: datetime,
        query_embedding: list[float],
        embedding_version: str,
        candidate_limit: int,
    ) -> PolicyRetrievalCandidatePage:
        if candidate_limit < 1 or candidate_limit > 256:
            raise ValueError("candidate_limit must be between 1 and 256")
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise PolicyNotFound("The actor organization was not found.")

        version = GovernedPolicyVersionModel
        base_filters = (
            version.organization_id == organization_id,
            version.status.in_(
                [
                    PolicyVersionStatus.PUBLISHED.value,
                    PolicyVersionStatus.SCHEDULED.value,
                ]
            ),
            version.immutable.is_(True),
        )
        category_match = _json_dimension_match(
            version.case_categories,
            {case_category},
        )
        applicability_match = and_(
            _json_dimension_match(version.products, products),
            _json_dimension_match(version.regions, {region}),
            _json_dimension_match(version.channels, {channel}),
            _json_dimension_match(version.customer_tiers, {customer_tier}),
        )
        effective_match = and_(
            or_(version.effective_from.is_(None), version.effective_from <= as_of),
            or_(version.effective_to.is_(None), version.effective_to > as_of),
        )
        counts = self._session.execute(
            select(
                func.count(distinct(version.policy_id)).filter(category_match),
                func.count(distinct(version.policy_id)).filter(
                    and_(category_match, applicability_match)
                ),
                func.count(distinct(version.policy_id)).filter(
                    and_(category_match, applicability_match, effective_match)
                ),
            ).where(*base_filters)
        ).one()
        category_matches = int(counts[0] or 0)
        applicable_matches = int(counts[1] or 0)
        active_matches = int(counts[2] or 0)
        active_filters = (
            *base_filters,
            category_match,
            applicability_match,
            effective_match,
        )
        conflicting_scopes = list(
            self._session.scalars(
                select(version.decision_scope)
                .where(*active_filters)
                .group_by(version.decision_scope)
                .having(func.count(distinct(version.policy_id)) > 1)
                .order_by(version.decision_scope)
            )
        )
        if active_matches == 0 or conflicting_scopes:
            return PolicyRetrievalCandidatePage(
                category_matches=category_matches,
                applicable_matches=applicable_matches,
                active_matches=active_matches,
                truncated=False,
                conflicting_scopes=conflicting_scopes,
                candidates=[],
            )

        distance = GovernedPolicyClauseModel.embedding.cosine_distance(query_embedding)
        clause_rows = self._session.execute(
            select(
                PolicyModel,
                version,
                GovernedPolicyClauseModel,
                (1.0 - distance).label("retrieval_score"),
            )
            .join(
                version,
                and_(
                    version.organization_id == PolicyModel.organization_id,
                    version.policy_id == PolicyModel.id,
                ),
            )
            .join(
                GovernedPolicyClauseModel,
                and_(
                    GovernedPolicyClauseModel.organization_id
                    == version.organization_id,
                    GovernedPolicyClauseModel.policy_id == version.policy_id,
                    GovernedPolicyClauseModel.policy_version_id == version.id,
                ),
            )
            .where(
                *active_filters,
                GovernedPolicyClauseModel.embedding_version == embedding_version,
            )
            .order_by(
                distance,
                PolicyModel.public_id,
                version.version.desc(),
                GovernedPolicyClauseModel.sequence,
            )
            .limit(candidate_limit)
        ).all()
        candidates: list[RankedPolicyCandidateRecord] = []
        seen_policies = set()
        for policy, active_version, clause, score in clause_rows:
            if policy.id in seen_policies:
                continue
            seen_policies.add(policy.id)
            candidates.append(
                RankedPolicyCandidateRecord(
                    candidate=PolicyCandidateRecord(
                        policy=PolicyRecord.model_validate(policy),
                        version=GovernedPolicyVersionRecord.model_validate(active_version),
                        clauses=[GovernedPolicyClauseRecord.model_validate(clause)],
                    ),
                    retrieval_score=max(-1.0, min(1.0, float(score))),
                )
            )
        return PolicyRetrievalCandidatePage(
            category_matches=category_matches,
            applicable_matches=applicable_matches,
            active_matches=active_matches,
            truncated=False,
            conflicting_scopes=[],
            candidates=candidates,
        )

    def list_evidence_for_case(
        self, *, organization_public_id: str, case_public_id: str
    ) -> list[PolicyEvidenceBundle]:
        rows = self._session.execute(
            select(
                CasePolicyEvidenceModel,
                PolicyModel,
                GovernedPolicyVersionModel,
                GovernedPolicyClauseModel,
            )
            .join(
                PolicyModel,
                and_(
                    PolicyModel.organization_id == CasePolicyEvidenceModel.organization_id,
                    PolicyModel.id == CasePolicyEvidenceModel.policy_id,
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
            .join(
                CaseModel,
                and_(
                    CaseModel.organization_id == CasePolicyEvidenceModel.organization_id,
                    CaseModel.id == CasePolicyEvidenceModel.case_id,
                ),
            )
            .join(
                OrganizationModel,
                OrganizationModel.id == CaseModel.organization_id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
            .order_by(CasePolicyEvidenceModel.recorded_at, CasePolicyEvidenceModel.public_id)
        ).all()
        return [
            PolicyEvidenceBundle(
                evidence=CasePolicyEvidenceRecord.model_validate(evidence),
                policy=PolicyRecord.model_validate(policy),
                version=GovernedPolicyVersionRecord.model_validate(version),
                clause=GovernedPolicyClauseRecord.model_validate(clause),
            )
            for evidence, policy, version, clause in rows
        ]
