from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.notifications import (
    NotificationKind,
    NotificationResourceType,
    NotificationSeed,
)
from app.domain.settings import NotificationSettingsValues, SettingsSection
from app.persistence.models import (
    CaseActionModel,
    CaseModel,
    CaseReviewModel,
    MembershipModel,
    OrganizationModel,
)
from app.persistence.notification_repository import NotificationRepository
from app.persistence.settings_repository import OrganizationSettingsRepository


class OperationalNotificationProjector:
    """Projects current operational states into idempotent in-app notifications."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._notifications = NotificationRepository(session)
        self._settings = OrganizationSettingsRepository(session)

    def project(
        self,
        *,
        organization_public_id: str,
        now: datetime | None = None,
    ) -> int:
        organization = self._session.scalar(
            select(OrganizationModel).where(
                OrganizationModel.public_id == organization_public_id
            )
        )
        if organization is None:
            return 0
        settings = self._settings.get(
            organization_public_id=organization_public_id,
            section=SettingsSection.NOTIFICATIONS,
        )
        if settings is None or not isinstance(
            settings.configuration,
            NotificationSettingsValues,
        ):
            return 0
        values = settings.configuration
        effective_now = now or datetime.now(UTC)
        active_members = list(
            self._session.scalars(
                select(MembershipModel).where(
                    MembershipModel.organization_id == organization.id,
                    MembershipModel.status == "active",
                )
            )
        )
        members_by_id = {member.id: member for member in active_members}
        supervisors = [
            member
            for member in active_members
            if member.role in {"supervisor", "administrator"}
        ]
        projected = 0

        if values.sla_risk_alerts:
            cases = self._session.scalars(
                select(CaseModel).where(
                    CaseModel.organization_id == organization.id,
                    CaseModel.status != "completed",
                    CaseModel.due_at <= effective_now + timedelta(hours=1),
                )
            )
            for case in cases:
                owner = members_by_id.get(case.owner_id) if case.owner_id else None
                recipients = [owner] if owner is not None else supervisors
                for recipient in recipients:
                    self._notifications.enqueue(
                        organization_public_id=organization_public_id,
                        seed=NotificationSeed(
                            recipient_public_id=recipient.public_id,
                            kind=NotificationKind.SLA_RISK,
                            title="Case response limit needs attention",
                            message=(
                                f"Case {case.public_id} is near or past its response "
                                "limit. Review the next action."
                            ),
                            resource_type=NotificationResourceType.CASE,
                            resource_public_id=case.public_id,
                            event_key=(
                                f"sla:{case.public_id}:{case.version}:"
                                f"{case.due_at.isoformat()}"
                            ),
                        ),
                        email_enabled=values.email_delivery,
                    )
                    projected += 1

        if values.review_waiting_alerts:
            reviews = self._session.scalars(
                select(CaseReviewModel).where(
                    CaseReviewModel.organization_id == organization.id,
                    CaseReviewModel.status.in_(["pending", "reserved"]),
                )
            )
            for review in reviews:
                for recipient in supervisors:
                    if recipient.id == review.submitted_by_id:
                        continue
                    self._notifications.enqueue(
                        organization_public_id=organization_public_id,
                        seed=NotificationSeed(
                            recipient_public_id=recipient.public_id,
                            kind=NotificationKind.REVIEW_WAITING,
                            title="A resolution is waiting for review",
                            message=(
                                f"Review {review.public_id} needs an authorized "
                                "decision."
                            ),
                            resource_type=NotificationResourceType.REVIEW,
                            resource_public_id=review.public_id,
                            event_key=f"review:{review.public_id}:{review.version}",
                        ),
                        email_enabled=values.email_delivery,
                    )
                    projected += 1

        if values.action_recovery_alerts:
            actions = self._session.scalars(
                select(CaseActionModel).where(
                    CaseActionModel.organization_id == organization.id,
                    or_(
                        CaseActionModel.status == "outcome_unknown",
                        CaseActionModel.status == "recovery_required",
                    ),
                )
            )
            for action in actions:
                for recipient in supervisors:
                    self._notifications.enqueue(
                        organization_public_id=organization_public_id,
                        seed=NotificationSeed(
                            recipient_public_id=recipient.public_id,
                            kind=NotificationKind.ACTION_RECOVERY,
                            title="An action outcome needs checking",
                            message=(
                                f"Action {action.public_id} must be checked before "
                                "another write is attempted."
                            ),
                            resource_type=NotificationResourceType.ACTION,
                            resource_public_id=action.public_id,
                            event_key=f"recovery:{action.public_id}:{action.version}",
                        ),
                        email_enabled=values.email_delivery,
                    )
                    projected += 1
        return projected
