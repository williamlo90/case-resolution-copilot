from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.domain.policies import (
    CasePolicyEvidenceRecord,
    PolicyEvidenceBinding,
    PolicyEvidenceBundle,
    PolicyVersionConcurrencyConflict,
    PolicyVersionStatus,
)
from app.persistence.models import (
    CasePolicyEvidenceModel,
    GovernedPolicyVersionModel,
    utc_now,
)
from app.retrieval.policy_parser import (
    GOVERNED_CORPUS_VERSION,
)

from ._base import (
    PolicyRepositoryBase,
)


class PolicyEvidenceRepository(PolicyRepositoryBase):
    def bind_evidence(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        bindings: list[PolicyEvidenceBinding],
        correlation_id: str,
    ) -> list[PolicyEvidenceBundle]:
        case = self._required_case(organization_public_id, case_public_id)
        bundles: list[PolicyEvidenceBundle] = []
        for binding in bindings:
            current_version = self._session.scalar(
                select(GovernedPolicyVersionModel).where(
                    GovernedPolicyVersionModel.id == binding.version.id,
                    GovernedPolicyVersionModel.organization_id == case.organization_id,
                    GovernedPolicyVersionModel.policy_id == binding.policy.id,
                    GovernedPolicyVersionModel.record_version == binding.version.record_version,
                    GovernedPolicyVersionModel.immutable.is_(True),
                    GovernedPolicyVersionModel.status.in_(
                        [
                            PolicyVersionStatus.PUBLISHED.value,
                            PolicyVersionStatus.SCHEDULED.value,
                        ]
                    ),
                )
            )
            if current_version is None:
                latest = self._session.scalar(
                    select(GovernedPolicyVersionModel.record_version).where(
                        GovernedPolicyVersionModel.id == binding.version.id,
                        GovernedPolicyVersionModel.organization_id == case.organization_id,
                    )
                )
                raise PolicyVersionConcurrencyConflict(
                    expected_version=binding.version.record_version,
                    current_version=latest or 1,
                )

            statement = (
                insert(CasePolicyEvidenceModel)
                .values(
                    id=uuid4(),
                    public_id=f"EVD-{uuid4().hex[:12].upper()}",
                    organization_id=case.organization_id,
                    case_id=case.id,
                    policy_id=binding.policy.id,
                    policy_version_id=binding.version.id,
                    clause_id=binding.clause.id,
                    citation=f"{binding.policy.title}, {binding.clause.heading}",
                    excerpt=binding.clause.text,
                    applicability=binding.applicability,
                    fingerprint=binding.fingerprint,
                    freshness="current",
                    conflict_state="none",
                    retrieval_score=binding.retrieval_score,
                    policy_content_hash=binding.version.content_hash,
                    clause_content_hash=binding.clause.content_hash,
                    effective_from=binding.version.effective_from,
                    effective_to=binding.version.effective_to,
                    corpus_version=GOVERNED_CORPUS_VERSION,
                    chunking_version=binding.clause.chunking_version,
                    embedding_version=binding.clause.embedding_version,
                    index_version=binding.clause.index_version,
                    embedding_profile_key=binding.embedding_profile_key,
                    retrieval_algorithm_version=binding.retrieval_algorithm_version,
                    query_fingerprint=binding.query_fingerprint,
                    dense_rank=binding.dense_rank,
                    lexical_rank=binding.lexical_rank,
                    fused_retrieval_score=binding.fused_retrieval_score,
                    retrieval_run_correlation_id=binding.retrieval_run_correlation_id,
                    recorded_at=utc_now(),
                )
                .on_conflict_do_nothing(
                    index_elements=["organization_id", "case_id", "fingerprint"]
                )
                .returning(CasePolicyEvidenceModel)
            )
            evidence = self._session.scalar(statement)
            if evidence is None:
                evidence = self._session.scalar(
                    select(CasePolicyEvidenceModel).where(
                        CasePolicyEvidenceModel.organization_id == case.organization_id,
                        CasePolicyEvidenceModel.case_id == case.id,
                        CasePolicyEvidenceModel.fingerprint == binding.fingerprint,
                    )
                )
            if evidence is None:
                raise RuntimeError("Policy evidence could not be persisted.")
            bundles.append(
                PolicyEvidenceBundle(
                    evidence=CasePolicyEvidenceRecord.model_validate(evidence),
                    policy=binding.policy,
                    version=binding.version,
                    clause=binding.clause,
                )
            )
        if bindings:
            self._audit_case_evidence(
                case=case,
                actor_id=actor_id,
                actor_type=actor_type,
                fingerprints=[binding.fingerprint for binding in bindings],
                correlation_id=correlation_id,
            )
        return bundles
