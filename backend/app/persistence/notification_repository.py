import base64
import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.domain.identity import ActorMembershipNotFound
from app.domain.notifications import (
    InvalidNotificationCursor,
    NotificationChannel,
    NotificationConflict,
    NotificationNotFound,
    NotificationPageRecord,
    NotificationRecord,
    NotificationSeed,
    NotificationStatus,
    NotificationVersionConflict,
    OutboxStatus,
)
from app.persistence.models import (
    MembershipModel,
    NotificationModel,
    NotificationOutboxModel,
    OrganizationModel,
)


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_actor(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        unread_only: bool,
        cursor: str | None,
        limit: int,
    ) -> NotificationPageRecord:
        organization, member = self._active_member(
            organization_public_id=organization_public_id,
            actor_id=actor_id,
        )
        conditions = [
            NotificationModel.organization_id == organization.id,
            NotificationModel.recipient_id == member.id,
        ]
        if unread_only:
            conditions.append(NotificationModel.status == NotificationStatus.UNREAD.value)
        filter_fingerprint = f"unread:{str(unread_only).lower()}"
        cursor_value: tuple[datetime, str] | None = None
        if cursor:
            cursor_value = _decode_cursor(cursor, filter_fingerprint)

        total = int(
            self._session.scalar(
                select(func.count(NotificationModel.id)).where(*conditions)
            )
            or 0
        )
        unread_count = int(
            self._session.scalar(
                select(func.count(NotificationModel.id)).where(
                    NotificationModel.organization_id == organization.id,
                    NotificationModel.recipient_id == member.id,
                    NotificationModel.status == NotificationStatus.UNREAD.value,
                )
            )
            or 0
        )
        statement = select(NotificationModel).where(*conditions)
        if cursor_value is not None:
            created_at, public_id = cursor_value
            statement = statement.where(
                or_(
                    NotificationModel.created_at < created_at,
                    and_(
                        NotificationModel.created_at == created_at,
                        NotificationModel.public_id < public_id,
                    ),
                )
            )
        models = list(
            self._session.scalars(
                statement.order_by(
                    NotificationModel.created_at.desc(),
                    NotificationModel.public_id.desc(),
                ).limit(limit + 1)
            )
        )
        has_next = len(models) > limit
        page_models = models[:limit]
        next_cursor = None
        if has_next and page_models:
            tail = page_models[-1]
            next_cursor = _encode_cursor(
                tail.created_at,
                tail.public_id,
                filter_fingerprint,
            )
        return NotificationPageRecord(
            items=[NotificationRecord.model_validate(model) for model in page_models],
            next_cursor=next_cursor,
            total=total,
            unread_count=unread_count,
        )

    def mark_read(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        notification_public_id: str,
        expected_version: int,
    ) -> NotificationRecord:
        organization, member = self._active_member(
            organization_public_id=organization_public_id,
            actor_id=actor_id,
        )
        notification = self._session.scalar(
            select(NotificationModel)
            .where(
                NotificationModel.organization_id == organization.id,
                NotificationModel.recipient_id == member.id,
                NotificationModel.public_id == notification_public_id,
            )
            .with_for_update()
        )
        if notification is None:
            raise NotificationNotFound("The notification was not found.")
        if notification.version != expected_version:
            raise NotificationVersionConflict(
                expected_version=expected_version,
                current_version=notification.version,
            )
        if notification.status == NotificationStatus.UNREAD.value:
            notification.status = NotificationStatus.READ.value
            notification.read_at = datetime.now(UTC)
            notification.version += 1
            self._session.flush()
        return NotificationRecord.model_validate(notification)

    def mark_all_read(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
    ) -> int:
        organization, member = self._active_member(
            organization_public_id=organization_public_id,
            actor_id=actor_id,
        )
        now = datetime.now(UTC)
        notifications = list(
            self._session.scalars(
                select(NotificationModel)
                .where(
                    NotificationModel.organization_id == organization.id,
                    NotificationModel.recipient_id == member.id,
                    NotificationModel.status == NotificationStatus.UNREAD.value,
                )
                .with_for_update()
            )
        )
        for notification in notifications:
            notification.status = NotificationStatus.READ.value
            notification.read_at = now
            notification.version += 1
        self._session.flush()
        return len(notifications)

    def enqueue(
        self,
        *,
        organization_public_id: str,
        seed: NotificationSeed,
        email_enabled: bool = False,
    ) -> NotificationRecord:
        organization = self._session.scalar(
            select(OrganizationModel).where(
                OrganizationModel.public_id == organization_public_id
            )
        )
        if organization is None:
            raise NotificationConflict("The notification organization was not found.")
        recipient = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization.id,
                MembershipModel.public_id == seed.recipient_public_id,
                MembershipModel.status == "active",
            )
        )
        if recipient is None:
            raise NotificationConflict("The notification recipient is not an active member.")
        existing = self._session.scalar(
            select(NotificationModel).where(
                NotificationModel.organization_id == organization.id,
                NotificationModel.recipient_id == recipient.id,
                NotificationModel.event_key == seed.event_key,
            )
        )
        if existing is not None:
            return NotificationRecord.model_validate(existing)

        now = datetime.now(UTC)
        public_id = _stable_public_id(
            "NTF",
            organization.public_id,
            recipient.public_id,
            seed.event_key,
        )
        notification = NotificationModel(
            public_id=public_id,
            organization_id=organization.id,
            recipient_id=recipient.id,
            recipient_public_id=recipient.public_id,
            kind=seed.kind.value,
            status=NotificationStatus.UNREAD.value,
            title=seed.title,
            message=seed.message,
            resource_type=seed.resource_type.value,
            resource_public_id=seed.resource_public_id,
            event_key=seed.event_key,
            version=1,
            created_at=now,
            read_at=None,
        )
        self._session.add(notification)
        self._session.flush()
        self._session.add(
            self._outbox_model(
                notification=notification,
                channel=NotificationChannel.IN_APP,
                status=OutboxStatus.DELIVERED,
                delivered_at=now,
            )
        )
        if email_enabled:
            self._session.add(
                self._outbox_model(
                    notification=notification,
                    channel=NotificationChannel.EMAIL,
                    status=OutboxStatus.PENDING,
                    delivered_at=None,
                )
            )
        self._session.flush()
        return NotificationRecord.model_validate(notification)

    def _active_member(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
    ) -> tuple[OrganizationModel, MembershipModel]:
        organization = self._session.scalar(
            select(OrganizationModel).where(
                OrganizationModel.public_id == organization_public_id
            )
        )
        if organization is None:
            raise ActorMembershipNotFound(
                "An active organization membership is required for notifications."
            )
        member = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization.id,
                MembershipModel.status == "active",
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        )
        if member is None:
            raise ActorMembershipNotFound(
                "An active organization membership is required for notifications."
            )
        return organization, member

    @staticmethod
    def _outbox_model(
        *,
        notification: NotificationModel,
        channel: NotificationChannel,
        status: OutboxStatus,
        delivered_at: datetime | None,
    ) -> NotificationOutboxModel:
        public_id = _stable_public_id(
            "OUT",
            notification.public_id,
            channel.value,
        )
        return NotificationOutboxModel(
            public_id=public_id,
            organization_id=notification.organization_id,
            notification_id=notification.id,
            channel=channel.value,
            status=status.value,
            destination_fingerprint=_destination_fingerprint(
                notification.organization_id,
                notification.recipient_public_id,
                channel,
            ),
            payload={
                "notification_id": notification.public_id,
                "kind": notification.kind,
                "resource_type": notification.resource_type,
                "resource_id": notification.resource_public_id,
            },
            attempt_count=0,
            available_at=notification.created_at,
            delivered_at=delivered_at,
            last_error_code=None,
            created_at=notification.created_at,
        )


def _stable_public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _destination_fingerprint(
    organization_id: UUID,
    recipient_public_id: str,
    channel: NotificationChannel,
) -> str:
    return sha256(
        f"{organization_id}:{recipient_public_id}:{channel.value}".encode()
    ).hexdigest()


def _encode_cursor(
    created_at: datetime,
    public_id: str,
    filter_fingerprint: str,
) -> str:
    payload = json.dumps(
        {
            "created_at": created_at.astimezone(UTC).isoformat(),
            "public_id": public_id,
            "filter": filter_fingerprint,
        },
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str, expected_filter: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        created_at = datetime.fromisoformat(payload["created_at"])
        public_id = str(payload["public_id"])
        filter_fingerprint = str(payload["filter"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidNotificationCursor("The notification cursor is invalid.") from exc
    if created_at.tzinfo is None or filter_fingerprint != expected_filter:
        raise InvalidNotificationCursor(
            "The notification cursor does not match these filters."
        )
    return created_at.astimezone(UTC), public_id
