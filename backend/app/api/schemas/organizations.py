from typing import Literal

from pydantic import EmailStr, Field, model_validator

from app.api.schemas.common import (
    ApiSchema,
    CursorPage,
    DataResponse,
    PublicId,
    UtcDateTime,
    Version,
)
from app.domain.identity import (
    ActorKind,
    AuthenticationMode,
    InvitationStatus,
    MemberRole,
    MemberStatus,
    Permission,
)


class OrganizationResponse(ApiSchema):
    id: PublicId
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    version: Version
    created_at: UtcDateTime
    updated_at: UtcDateTime


class MemberResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role: MemberRole
    status: MemberStatus
    authority: list[str]
    version: Version
    last_active_at: UtcDateTime | None


class InvitationResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    email: EmailStr
    role: MemberRole
    status: InvitationStatus
    version: Version
    invited_by: PublicId
    expires_at: UtcDateTime
    accepted_at: UtcDateTime | None


class MemberListResponse(CursorPage[MemberResponse]):
    pass


class MemberDetailResponse(DataResponse[MemberResponse]):
    pass


class SessionOrganizationResponse(ApiSchema):
    id: PublicId
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    version: Version
    locale: str = Field(pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$", max_length=16)
    time_zone: str = Field(min_length=1, max_length=100)


class SessionActorResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    name: str = Field(min_length=1, max_length=200)
    kind: ActorKind
    role: MemberRole | None
    permissions: list[Permission]
    authentication_mode: AuthenticationMode
    organization: SessionOrganizationResponse | None = None


class SessionResponse(DataResponse[SessionActorResponse]):
    pass


class OrganizationDetailResponse(DataResponse[OrganizationResponse]):
    pass


class CreateInvitationRequest(ApiSchema):
    email: EmailStr
    role: MemberRole


class UpdateMemberRequest(ApiSchema):
    expected_version: Version
    role: MemberRole | None = None
    status: Literal["active", "deactivated"] | None = None

    @model_validator(mode="after")
    def require_change(self) -> "UpdateMemberRequest":
        if self.role is None and self.status is None:
            raise ValueError("role or status is required")
        return self


class RevokeInvitationRequest(ApiSchema):
    expected_version: Version


class InvitationDetailResponse(DataResponse[InvitationResponse]):
    pass


class InvitationListResponse(CursorPage[InvitationResponse]):
    pass
