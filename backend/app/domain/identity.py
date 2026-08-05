from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class MemberRole(StrEnum):
    SPECIALIST = "specialist"
    SUPERVISOR = "supervisor"
    ADMINISTRATOR = "administrator"
    AUDITOR = "auditor"


def role_satisfies(*, actor_role: MemberRole | None, required_role: MemberRole) -> bool:
    if actor_role is MemberRole.ADMINISTRATOR:
        return True
    return actor_role is required_role


class MemberStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    DEACTIVATED = "deactivated"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ActorKind(StrEnum):
    MEMBER = "member"
    SERVICE = "service"
    SYSTEM = "system"


class AuthenticationMode(StrEnum):
    DETERMINISTIC_DEVELOPMENT = "deterministic_development"
    PROVIDER = "provider"


class Permission(StrEnum):
    SESSION_READ = "session:read"
    ORGANIZATION_READ = "organization:read"
    MEMBER_READ = "member:read"
    MEMBER_INVITE = "member:invite"
    MEMBER_MANAGE = "member:manage"
    CASE_READ = "case:read"
    CASE_MANAGE = "case:manage"
    REVIEW_READ = "review:read"
    REVIEW_RESERVE = "review:reserve"
    REVIEW_DECIDE = "review:decide"
    ACTION_READ = "action:read"
    ACTION_EXECUTE = "action:execute"
    ACTION_RECONCILE = "action:reconcile"
    POLICY_READ = "policy:read"
    POLICY_MANAGE = "policy:manage"
    CONNECTION_READ = "connection:read"
    CONNECTION_MANAGE = "connection:manage"
    QUALITY_READ = "quality:read"
    AUDIT_READ = "audit:read"
    SETTINGS_MANAGE = "settings:manage"


class OrganizationNotFound(LookupError):
    pass


class ActorMembershipNotFound(LookupError):
    pass


class ActorMembershipAmbiguous(RuntimeError):
    pass


class InvitationConflict(RuntimeError):
    pass


class MemberNotFound(LookupError):
    pass


class InvitationNotFound(LookupError):
    pass


class MemberConflict(RuntimeError):
    pass


class MemberVersionConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The member changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


class InvitationVersionConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The invitation changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


ROLE_PERMISSIONS: dict[MemberRole, frozenset[Permission]] = {
    MemberRole.SPECIALIST: frozenset(
        {
            Permission.SESSION_READ,
            Permission.ORGANIZATION_READ,
            Permission.MEMBER_READ,
            Permission.CASE_READ,
            Permission.CASE_MANAGE,
            Permission.REVIEW_READ,
            Permission.ACTION_READ,
            Permission.POLICY_READ,
            Permission.CONNECTION_READ,
        }
    ),
    MemberRole.SUPERVISOR: frozenset(
        {
            Permission.SESSION_READ,
            Permission.ORGANIZATION_READ,
            Permission.MEMBER_READ,
            Permission.CASE_READ,
            Permission.CASE_MANAGE,
            Permission.REVIEW_READ,
            Permission.REVIEW_RESERVE,
            Permission.REVIEW_DECIDE,
            Permission.ACTION_READ,
            Permission.ACTION_EXECUTE,
            Permission.ACTION_RECONCILE,
            Permission.POLICY_READ,
            Permission.CONNECTION_READ,
            Permission.QUALITY_READ,
        }
    ),
    MemberRole.ADMINISTRATOR: frozenset(Permission),
    MemberRole.AUDITOR: frozenset(
        {
            Permission.SESSION_READ,
            Permission.ORGANIZATION_READ,
            Permission.MEMBER_READ,
            Permission.CASE_READ,
            Permission.REVIEW_READ,
            Permission.ACTION_READ,
            Permission.POLICY_READ,
            Permission.CONNECTION_READ,
            Permission.QUALITY_READ,
            Permission.AUDIT_READ,
        }
    ),
}


class ActorOrganizationContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    slug: str
    version: int
    locale: str
    time_zone: str


class ActorContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor_id: str
    organization_id: str
    name: str
    kind: ActorKind
    role: MemberRole | None
    permissions: frozenset[Permission]
    authentication_mode: AuthenticationMode
    organization: ActorOrganizationContext | None = None

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


class OrganizationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    name: str
    slug: str
    version: int
    created_at: datetime
    updated_at: datetime


class MemberRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    subject_id: str
    name: str
    email: EmailStr
    role: MemberRole
    status: MemberStatus
    version: int
    last_active_at: datetime | None


class InvitationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    email: EmailStr
    role: MemberRole
    status: InvitationStatus
    version: int
    invited_by: str
    provider_invitation_id: str | None = None
    expires_at: datetime
    accepted_at: datetime | None


class InvitedIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject_id: str
    email: EmailStr
    name: str
    invitation_id: str | None = None
    organization_id: str | None = None
    role: str | None = None
