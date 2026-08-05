from app.api.schemas.notifications import NotificationResponse
from app.domain.notifications import NotificationRecord


def present_notification(
    record: NotificationRecord,
    *,
    organization_id: str,
) -> NotificationResponse:
    return NotificationResponse(
        id=record.public_id,
        organization_id=organization_id,
        kind=record.kind,
        status=record.status,
        title=record.title,
        message=record.message,
        resource_type=record.resource_type,
        resource_id=record.resource_public_id,
        version=record.version,
        created_at=record.created_at,
        read_at=record.read_at,
    )
