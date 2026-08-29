from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.policy_indexing import PolicyIndexWorkItem
from app.domain.retrieval_v2 import PolicyIndexJobRecord
from app.persistence.models import (
    GovernedPolicyClauseEmbeddingV2Model,
    GovernedPolicyClauseModel,
    PolicyEmbeddingProfileModel,
    PolicyIndexJobModel,
)

from .profile_counts import refresh_profile_counts


def persist_page(
    session: Session,
    *,
    work: PolicyIndexWorkItem,
    vectors: tuple[list[float], ...],
    now: datetime,
) -> PolicyIndexJobRecord:
    if len(vectors) != len(work.clauses):
        raise ValueError("The embedding response count does not match the clause page.")
    job = _leased_job(session, work, now=now)
    indexed = skipped = 0
    for clause, vector in zip(work.clauses, vectors, strict=True):
        if len(vector) != work.profile.dimensions or not all(
            float("-inf") < value < float("inf") for value in vector
        ):
            raise ValueError("The embedding provider returned an invalid policy vector.")
        current = session.scalar(
            select(GovernedPolicyClauseModel).where(
                GovernedPolicyClauseModel.id == clause.id,
                GovernedPolicyClauseModel.organization_id == clause.organization_id,
                GovernedPolicyClauseModel.policy_version_id == clause.policy_version_id,
                GovernedPolicyClauseModel.content_hash == clause.content_hash,
            )
        )
        if current is None:
            skipped += 1
            continue
        _upsert_embedding(session, work, clause.content_hash, clause.id, vector, now)
        indexed += 1
    _finish_page(session, job, work, indexed=indexed, skipped=skipped, now=now)
    return PolicyIndexJobRecord.model_validate(job)


def fail(
    session: Session,
    *,
    work: PolicyIndexWorkItem,
    error_code: str,
    now: datetime,
    max_attempts: int,
) -> PolicyIndexJobRecord:
    job = _leased_job(session, work, now=now)
    job.status = "dead" if job.attempt_count >= max_attempts else "failed"
    job.last_error_code = error_code[:100]
    job.available_at = now + timedelta(minutes=min(2**job.attempt_count, 60))
    job.lease_owner = None
    job.lease_expires_at = None
    session.flush()
    return PolicyIndexJobRecord.model_validate(job)


def _upsert_embedding(
    session: Session,
    work: PolicyIndexWorkItem,
    content_hash: str,
    clause_id: UUID,
    vector: list[float],
    now: datetime,
) -> None:
    request_fingerprint = sha256(f"{work.profile.profile_key}|{content_hash}".encode()).hexdigest()
    clause = next(item for item in work.clauses if item.id == clause_id)
    session.execute(
        insert(GovernedPolicyClauseEmbeddingV2Model)
        .values(
            id=uuid4(),
            organization_id=clause.organization_id,
            policy_id=clause.policy_id,
            policy_version_id=clause.policy_version_id,
            clause_id=clause.id,
            profile_id=work.profile.id,
            source_content_hash=content_hash,
            embedding=vector,
            provider_request_fingerprint=request_fingerprint,
            indexed_at=now,
        )
        .on_conflict_do_update(
            index_elements=["organization_id", "clause_id", "profile_id"],
            set_={
                "source_content_hash": content_hash,
                "embedding": vector,
                "provider_request_fingerprint": request_fingerprint,
                "indexed_at": now,
            },
        )
    )


def _leased_job(
    session: Session,
    work: PolicyIndexWorkItem,
    *,
    now: datetime,
) -> PolicyIndexJobModel:
    job = session.scalar(
        select(PolicyIndexJobModel)
        .where(
            PolicyIndexJobModel.id == work.job.id,
            PolicyIndexJobModel.profile_id == work.profile.id,
            PolicyIndexJobModel.status == "running",
            PolicyIndexJobModel.lease_owner == work.job.lease_owner,
            PolicyIndexJobModel.attempt_count == work.job.attempt_count,
            PolicyIndexJobModel.lease_expires_at > now,
        )
        .with_for_update()
    )
    if job is None:
        raise RuntimeError("The policy index lease is no longer current.")
    return job


def _finish_page(
    session: Session,
    job: PolicyIndexJobModel,
    work: PolicyIndexWorkItem,
    *,
    indexed: int,
    skipped: int,
    now: datetime,
) -> None:
    job.indexed_clause_count += indexed
    job.skipped_clause_count += skipped
    if _remaining_clause_count(session, job) == 0:
        job.status = "completed"
        job.completed_at = now
        job.last_error_code = None
    else:
        job.status = "pending"
        job.available_at = now
    job.lease_owner = None
    job.lease_expires_at = None
    profile = session.get(PolicyEmbeddingProfileModel, work.profile.id)
    if profile is None:
        raise RuntimeError("The policy embedding profile was removed.")
    refresh_profile_counts(session, profile)
    session.flush()


def _remaining_clause_count(session: Session, job: PolicyIndexJobModel) -> int:
    clause = GovernedPolicyClauseModel
    embedding = GovernedPolicyClauseEmbeddingV2Model
    return (
        session.scalar(
            select(func.count(clause.id))
            .outerjoin(
                embedding,
                and_(
                    embedding.organization_id == clause.organization_id,
                    embedding.clause_id == clause.id,
                    embedding.profile_id == job.profile_id,
                    embedding.source_content_hash == clause.content_hash,
                ),
            )
            .where(
                clause.organization_id == job.organization_id,
                clause.policy_version_id == job.policy_version_id,
                embedding.id.is_(None),
            )
        )
        or 0
    )
