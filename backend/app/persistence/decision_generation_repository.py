from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.decision_briefs import (
    CompletedDecisionGeneration,
    DecisionGenerationInProgress,
    DecisionGenerationLease,
    DecisionGenerationLeaseLost,
    DecisionGenerationRetryExhausted,
    DecisionGenerationStatus,
)
from app.domain.policies import PolicyNotFound
from app.persistence.models import (
    CaseAnalysisGenerationModel,
    CaseModel,
    OrganizationModel,
)


class DecisionGenerationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def acquire(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        input_fingerprint: str,
        lease_seconds: int,
        max_attempts: int,
    ) -> DecisionGenerationLease | CompletedDecisionGeneration:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        organization_id, case_id = self._scope_ids(
            organization_public_id=organization_public_id,
            case_public_id=case_public_id,
        )
        now = datetime.now(UTC)
        owner_token = uuid4()
        row = CaseAnalysisGenerationModel(
            organization_id=organization_id,
            case_id=case_id,
            input_fingerprint=input_fingerprint,
            owner_token=owner_token,
            fence_token=1,
            attempt_count=1,
            status=DecisionGenerationStatus.RUNNING.value,
            expires_at=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
            return _lease(row)
        except IntegrityError:
            # A concurrent insert can block until its transaction resolves. Refresh the
            # clock before deciding whether the winning lease is still active.
            now = datetime.now(UTC)

        existing = self._session.scalar(
            select(CaseAnalysisGenerationModel)
            .where(
                CaseAnalysisGenerationModel.organization_id == organization_id,
                CaseAnalysisGenerationModel.case_id == case_id,
                CaseAnalysisGenerationModel.input_fingerprint == input_fingerprint,
            )
            .with_for_update()
        )
        if existing is None:
            raise DecisionGenerationLeaseLost(
                "The decision generation reservation disappeared during acquisition."
            )
        if existing.status == DecisionGenerationStatus.RUNNING.value and existing.expires_at > now:
            raise DecisionGenerationInProgress(
                retry_after_seconds=ceil((existing.expires_at - now).total_seconds())
            )
        if existing.status == DecisionGenerationStatus.COMPLETED.value:
            if existing.analysis_run_id is None:
                raise DecisionGenerationLeaseLost(
                    "The completed generation has no reusable analysis run."
                )
            return CompletedDecisionGeneration(
                input_fingerprint=existing.input_fingerprint,
                analysis_run_id=existing.analysis_run_id,
            )
        if existing.attempt_count >= max_attempts:
            raise DecisionGenerationRetryExhausted(
                "Decision generation retry limit reached for this input snapshot."
            )

        existing.owner_token = owner_token
        existing.fence_token += 1
        existing.attempt_count += 1
        existing.status = DecisionGenerationStatus.RUNNING.value
        existing.expires_at = now + timedelta(seconds=lease_seconds)
        existing.analysis_run_id = None
        existing.last_error_code = None
        existing.completed_at = None
        existing.updated_at = now
        self._session.flush()
        return _lease(existing)

    def complete(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        lease: DecisionGenerationLease,
        analysis_run_id: UUID,
    ) -> None:
        organization_id, case_id = self._scope_ids(
            organization_public_id=organization_public_id,
            case_public_id=case_public_id,
        )
        now = datetime.now(UTC)
        result = cast(
            CursorResult[Any],
            self._session.execute(
                update(CaseAnalysisGenerationModel)
                .where(
                    CaseAnalysisGenerationModel.organization_id == organization_id,
                    CaseAnalysisGenerationModel.case_id == case_id,
                    CaseAnalysisGenerationModel.input_fingerprint == lease.input_fingerprint,
                    CaseAnalysisGenerationModel.owner_token == lease.owner_token,
                    CaseAnalysisGenerationModel.fence_token == lease.fence_token,
                    CaseAnalysisGenerationModel.status == DecisionGenerationStatus.RUNNING.value,
                )
                .values(
                    status=DecisionGenerationStatus.COMPLETED.value,
                    analysis_run_id=analysis_run_id,
                    completed_at=now,
                    expires_at=now,
                    updated_at=now,
                    last_error_code=None,
                )
                .execution_options(synchronize_session=False)
            ),
        )
        if result.rowcount != 1:
            raise DecisionGenerationLeaseLost(
                "Decision generation ownership expired before the result was saved."
            )

    def fail(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        lease: DecisionGenerationLease,
        error_code: str,
    ) -> bool:
        organization_id, case_id = self._scope_ids(
            organization_public_id=organization_public_id,
            case_public_id=case_public_id,
        )
        now = datetime.now(UTC)
        result = cast(
            CursorResult[Any],
            self._session.execute(
                update(CaseAnalysisGenerationModel)
                .where(
                    CaseAnalysisGenerationModel.organization_id == organization_id,
                    CaseAnalysisGenerationModel.case_id == case_id,
                    CaseAnalysisGenerationModel.input_fingerprint == lease.input_fingerprint,
                    CaseAnalysisGenerationModel.owner_token == lease.owner_token,
                    CaseAnalysisGenerationModel.fence_token == lease.fence_token,
                    CaseAnalysisGenerationModel.status == DecisionGenerationStatus.RUNNING.value,
                )
                .values(
                    status=DecisionGenerationStatus.FAILED.value,
                    expires_at=now,
                    updated_at=now,
                    last_error_code=error_code[:64],
                )
                .execution_options(synchronize_session=False)
            ),
        )
        return result.rowcount == 1

    def _scope_ids(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> tuple[UUID, UUID]:
        row = self._session.execute(
            select(OrganizationModel.id, CaseModel.id)
            .join(CaseModel, CaseModel.organization_id == OrganizationModel.id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
        ).one_or_none()
        if row is None:
            raise PolicyNotFound("The case was not found.")
        return row[0], row[1]


def _lease(row: CaseAnalysisGenerationModel) -> DecisionGenerationLease:
    return DecisionGenerationLease(
        input_fingerprint=row.input_fingerprint,
        owner_token=row.owner_token,
        fence_token=row.fence_token,
        attempt=row.attempt_count,
        expires_at=row.expires_at,
    )
