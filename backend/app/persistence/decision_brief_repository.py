from sqlalchemy.orm import Session

from app.domain.decision_briefs import (
    DecisionBriefCreate,
    DecisionBriefRecord,
)
from app.persistence.decision_brief_queries import DecisionBriefQueryRepository
from app.persistence.decision_brief_writer import DecisionBriefWriter


class DecisionBriefRepository:
    """Stable facade over decision brief query and write capabilities."""

    def __init__(self, session: Session) -> None:
        self._queries = DecisionBriefQueryRepository(session)
        self._writer = DecisionBriefWriter(session, self._queries)

    def get_latest(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> DecisionBriefRecord | None:
        return self._queries.get_latest(
            organization_public_id=organization_public_id,
            case_public_id=case_public_id,
        )

    def get_version(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        version: int,
    ) -> DecisionBriefRecord | None:
        return self._queries.get_version(
            organization_public_id=organization_public_id,
            case_public_id=case_public_id,
            version=version,
        )

    def get_by_input_fingerprint(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        input_fingerprint: str,
    ) -> DecisionBriefRecord | None:
        return self._queries.get_by_input_fingerprint(
            organization_public_id=organization_public_id,
            case_public_id=case_public_id,
            input_fingerprint=input_fingerprint,
        )

    def create_or_get(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        command: DecisionBriefCreate,
        correlation_id: str,
    ) -> DecisionBriefRecord:
        return self._writer.create_or_get(
            organization_public_id=organization_public_id,
            case_public_id=case_public_id,
            actor_id=actor_id,
            actor_type=actor_type,
            command=command,
            correlation_id=correlation_id,
        )
