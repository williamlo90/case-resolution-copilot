from pydantic import Field

from app.api.schemas.common import (
    ApiSchema,
    CursorPage,
    DataResponse,
    PublicId,
    UtcDateTime,
    Version,
)
from app.domain.notifications import (
    NotificationKind,
    NotificationResourceType,
    NotificationStatus,
)


class NotificationResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    kind: NotificationKind
    status: NotificationStatus
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)
    resource_type: NotificationResourceType
    resource_id: PublicId
    version: Version
    created_at: UtcDateTime
    read_at: UtcDateTime | None


class NotificationListResponse(CursorPage[NotificationResponse]):
    unread_count: int = Field(ge=0)


class MarkNotificationReadRequest(ApiSchema):
    expected_version: Version


class MarkAllNotificationsReadResponse(ApiSchema):
    updated: int = Field(ge=0)


class NotificationDetailEnvelope(DataResponse[NotificationResponse]):
    pass


class MarkAllNotificationsReadEnvelope(
    DataResponse[MarkAllNotificationsReadResponse]
):
    pass
