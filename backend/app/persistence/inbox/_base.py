from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.identity import ActorMembershipNotFound
from app.domain.inbox import InboxNotFound
from app.persistence.models import (
    AuditEventModel,
    ConnectionModel,
    MembershipModel,
    OrganizationModel,
    utc_now,
)


class InboxRepositoryBase:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _organization(self, public_id: str) -> OrganizationModel:
        organization = self._session.scalar(
            select(OrganizationModel).where(OrganizationModel.public_id == public_id)
        )
        if organization is None:
            raise InboxNotFound("The workspace was not found.")
        return organization

    def _member(self, organization_id: UUID, actor_id: str) -> MembershipModel:
        member = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization_id,
                MembershipModel.status == "active",
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        )
        if member is None:
            raise ActorMembershipNotFound(
                "An active workspace membership is required for this inbox."
            )
        return member

    def _connection(
        self,
        organization_public_id: str,
        connection_public_id: str,
        *,
        for_update: bool = False,
    ) -> ConnectionModel:
        statement = (
            select(ConnectionModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == ConnectionModel.organization_id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                ConnectionModel.public_id == connection_public_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        connection = self._session.scalar(statement)
        if connection is None:
            raise InboxNotFound("The inbox connection was not found.")
        return connection

    def _audit(
        self,
        *,
        organization_id: UUID,
        event_type: str,
        actor_id: str | None,
        subject_id: str,
        summary: str,
        data: dict[str, Any],
        correlation_id: str,
    ) -> None:
        self._session.add(
            AuditEventModel(
                organization_id=organization_id,
                task_id=None,
                run_id=None,
                event_type=event_type,
                actor_type="member" if actor_id else "system",
                actor_id=actor_id,
                subject_type="connection",
                subject_id=subject_id,
                summary=summary,
                data=data,
                correlation_id=correlation_id,
                occurred_at=utc_now(),
            )
        )
