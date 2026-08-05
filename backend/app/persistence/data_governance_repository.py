import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.settings import RetentionSettingsValues
from app.persistence.models import (
    CaseDataGovernanceModel,
    CaseModel,
    OrganizationModel,
)
from app.persistence.settings_repository import OrganizationSettingsRepository


class DataGovernanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def backfill(
        self,
        *,
        organization_public_id: str,
        apply: bool,
        now: datetime | None = None,
    ) -> tuple[int, int]:
        organization = self._session.scalar(
            select(OrganizationModel).where(
                OrganizationModel.public_id == organization_public_id
            )
        )
        if organization is None:
            return 0, 0
        retention, policy_version = OrganizationSettingsRepository(
            self._session
        ).retention_values(organization_public_id=organization_public_id)
        cases = list(
            self._session.scalars(
                select(CaseModel)
                .outerjoin(
                    CaseDataGovernanceModel,
                    CaseDataGovernanceModel.case_id == CaseModel.id,
                )
                .where(
                    CaseModel.organization_id == organization.id,
                    CaseDataGovernanceModel.id.is_(None),
                )
                .order_by(CaseModel.public_id)
            )
        )
        if not apply:
            return len(cases), 0
        effective_now = now or datetime.now(UTC)
        for case in cases:
            conversation_until = case.created_at + timedelta(
                days=retention.conversation_retention_days
            )
            audit_until = case.created_at + timedelta(
                days=retention.audit_retention_days
            )
            status = "due" if conversation_until <= effective_now else "active"
            self._session.add(
                CaseDataGovernanceModel(
                    public_id=_stable_public_id(
                        "DGV",
                        organization.public_id,
                        case.public_id,
                    ),
                    organization_id=organization.id,
                    case_id=case.id,
                    retention_policy_version=policy_version,
                    conversation_retention_until=conversation_until,
                    audit_retention_until=audit_until,
                    redaction_status=status,
                    legal_hold=False,
                    redacted_at=None,
                    source_fingerprint=_source_fingerprint(
                        case_public_id=case.public_id,
                        case_created_at=case.created_at,
                        settings=retention,
                        policy_version=policy_version,
                    ),
                    version=1,
                    created_at=effective_now,
                    updated_at=effective_now,
                )
            )
        self._session.flush()
        return len(cases), len(cases)


def _source_fingerprint(
    *,
    case_public_id: str,
    case_created_at: datetime,
    settings: RetentionSettingsValues,
    policy_version: int,
) -> str:
    return sha256(
        json.dumps(
            {
                "case_id": case_public_id,
                "case_created_at": case_created_at.astimezone(UTC).isoformat(),
                "settings": settings.model_dump(mode="json"),
                "policy_version": policy_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _stable_public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"
