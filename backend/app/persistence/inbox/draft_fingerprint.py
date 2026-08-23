from hashlib import sha256
from uuid import UUID

from app.domain.inbox import (
    CaseDraftContext,
    InboxReplyContext,
    ReviewDraftAuthorization,
)


def draft_delivery_key(
    *,
    organization_id: UUID,
    case: CaseDraftContext,
    reply: InboxReplyContext,
    review: ReviewDraftAuthorization,
) -> str:
    material = (
        str(organization_id),
        str(case.response_draft_id),
        str(case.response_draft_version),
        review.snapshot_fingerprint,
        review.evidence_fingerprint,
        review.policy_fingerprint,
        reply.conversation_fingerprint,
        case.response_fingerprint,
    )
    return sha256("\0".join(material).encode("utf-8")).hexdigest()
