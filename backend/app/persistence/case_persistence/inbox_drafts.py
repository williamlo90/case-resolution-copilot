import json
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.inbox import (
    CaseDraftContext,
    InboxConflict,
    InboxNotFound,
    response_content_fingerprint,
)
from app.persistence.models import CaseModel, OrganizationModel, ResponseDraftModel


class CaseDraftReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def current(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        expected_draft_version: int,
    ) -> CaseDraftContext:
        row = self._session.execute(
            select(CaseModel, ResponseDraftModel)
            .join(OrganizationModel, OrganizationModel.id == CaseModel.organization_id)
            .join(
                ResponseDraftModel,
                (ResponseDraftModel.organization_id == CaseModel.organization_id)
                & (ResponseDraftModel.case_id == CaseModel.id),
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
        ).one_or_none()
        if row is None:
            raise InboxNotFound("The case response draft was not found.")
        case, draft = row
        if draft.version != expected_draft_version:
            raise InboxConflict("The response draft changed. Review the latest version first.")
        if draft.status != "ready":
            raise InboxConflict(
                "The response draft is not approved and ready for Gmail."
            )
        fingerprint = sha256(
            json.dumps(
                {
                    "draft_id": draft.public_id,
                    "version": draft.version,
                    "subject": draft.subject,
                    "body": draft.body,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return CaseDraftContext(
            organization_id=case.organization_id,
            case_id=case.id,
            case_public_id=case.public_id,
            case_version=case.version,
            response_draft_id=draft.id,
            response_draft_version=draft.version,
            subject=draft.subject,
            body=draft.body,
            response_fingerprint=fingerprint,
            response_content_fingerprint=response_content_fingerprint(
                subject=draft.subject,
                body=draft.body,
            ),
        )
