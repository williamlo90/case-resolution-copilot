from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.dml import Insert

from app.domain.policy_indexing import PolicyIndexClauseRecord, PolicyIndexWorkItem
from app.domain.retrieval_v2 import (
    EmbeddingProfileRecord,
    PolicyIndexJobRecord,
    PolicyIndexJobStatus,
)
from app.persistence.models import (
    GovernedPolicyClauseEmbeddingV2Model,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    PolicyEmbeddingProfileModel,
    PolicyIndexJobModel,
    utc_now,
)

from .profile_counts import refresh_profile_counts

_ACTIVE_VERSION_STATES = ("published", "scheduled")


def enqueue_missing(
    session: Session,
    *,
    profile_key: str,
    job_limit: int,
    page_budget: int,
) -> int:
    if job_limit < 1 or page_budget < 1:
        raise ValueError("Policy index job limits must be positive.")
    profile = required_profile(session, profile_key)
    existing = aliased(PolicyIndexJobModel)
    versions = session.scalars(
        select(GovernedPolicyVersionModel)
        .where(
            GovernedPolicyVersionModel.status.in_(_ACTIVE_VERSION_STATES),
            GovernedPolicyVersionModel.immutable.is_(True),
            ~exists(
                select(existing.id).where(
                    existing.profile_id == profile.id,
                    existing.policy_version_id == GovernedPolicyVersionModel.id,
                    existing.source_content_fingerprint
                    == GovernedPolicyVersionModel.content_hash,
                )
            ),
        )
        .order_by(GovernedPolicyVersionModel.created_at, GovernedPolicyVersionModel.id)
        .limit(job_limit)
    )
    created = 0
    for version in versions:
        job_key = sha256(
            f"{profile.profile_key}|{version.id}|{version.content_hash}".encode()
        ).hexdigest()
        inserted_id = session.scalar(
            _enqueue_statement(
                organization_id=version.organization_id,
                policy_id=version.policy_id,
                policy_version_id=version.id,
                profile_id=profile.id,
                source_content_fingerprint=version.content_hash,
                job_key=job_key,
                page_budget=min(page_budget, 32),
            )
        )
        created += int(inserted_id is not None)
    refresh_profile_counts(session, profile)
    session.flush()
    return created


def _enqueue_statement(
    *,
    organization_id: UUID,
    policy_id: UUID,
    policy_version_id: UUID,
    profile_id: UUID,
    source_content_fingerprint: str,
    job_key: str,
    page_budget: int,
) -> Insert:
    now = utc_now()
    return (
        postgresql_insert(PolicyIndexJobModel)
        .values(
            id=uuid4(),
            public_id=f"PIJ-{job_key[:16].upper()}",
            organization_id=organization_id,
            policy_id=policy_id,
            policy_version_id=policy_version_id,
            profile_id=profile_id,
            source_content_fingerprint=source_content_fingerprint,
            job_key=job_key,
            status=PolicyIndexJobStatus.PENDING.value,
            page_budget=page_budget,
            attempt_count=0,
            available_at=now,
            lease_owner=None,
            lease_expires_at=None,
            last_error_code=None,
            indexed_clause_count=0,
            skipped_clause_count=0,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_policy_index_jobs_key")
        .returning(PolicyIndexJobModel.id)
    )


def claim(
    session: Session,
    *,
    profile_key: str,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
) -> PolicyIndexWorkItem | None:
    profile = required_profile(session, profile_key)
    job = session.scalar(
        select(PolicyIndexJobModel)
        .where(
            PolicyIndexJobModel.profile_id == profile.id,
            PolicyIndexJobModel.available_at <= now,
            or_(
                PolicyIndexJobModel.status.in_(["pending", "failed"]),
                and_(
                    PolicyIndexJobModel.status == "running",
                    PolicyIndexJobModel.lease_expires_at < now,
                ),
            ),
        )
        .order_by(PolicyIndexJobModel.available_at, PolicyIndexJobModel.created_at)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.status = PolicyIndexJobStatus.RUNNING.value
    job.attempt_count += 1
    job.lease_owner = worker_id
    job.lease_expires_at = lease_expires_at
    clauses = _pending_clauses(session, job)
    session.flush()
    return PolicyIndexWorkItem(
        job=PolicyIndexJobRecord.model_validate(job),
        profile=EmbeddingProfileRecord.model_validate(profile),
        clauses=tuple(PolicyIndexClauseRecord.model_validate(item) for item in clauses),
        lease_expires_at=lease_expires_at,
    )


def required_profile(
    session: Session,
    profile_key: str,
) -> PolicyEmbeddingProfileModel:
    profile = session.scalar(
        select(PolicyEmbeddingProfileModel).where(
            PolicyEmbeddingProfileModel.profile_key == profile_key,
            PolicyEmbeddingProfileModel.status.not_in(["retired", "failed"]),
        )
    )
    if profile is None:
        raise LookupError("The policy embedding profile is not available.")
    return profile


def _pending_clauses(
    session: Session,
    job: PolicyIndexJobModel,
) -> list[GovernedPolicyClauseModel]:
    embedding = aliased(GovernedPolicyClauseEmbeddingV2Model)
    return list(
        session.scalars(
            select(GovernedPolicyClauseModel)
            .outerjoin(
                embedding,
                and_(
                    embedding.organization_id
                    == GovernedPolicyClauseModel.organization_id,
                    embedding.clause_id == GovernedPolicyClauseModel.id,
                    embedding.profile_id == job.profile_id,
                ),
            )
            .where(
                GovernedPolicyClauseModel.organization_id == job.organization_id,
                GovernedPolicyClauseModel.policy_version_id == job.policy_version_id,
                or_(
                    embedding.id.is_(None),
                    embedding.source_content_hash != GovernedPolicyClauseModel.content_hash,
                ),
            )
            .order_by(GovernedPolicyClauseModel.sequence)
            .limit(job.page_budget)
        )
    )
