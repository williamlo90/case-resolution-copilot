from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class OrganizationModel(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_organizations_version_positive"),
        UniqueConstraint("public_id", name="uq_organizations_public_id"),
        UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class MembershipModel(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_memberships_version_positive"),
        CheckConstraint(
            "role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_memberships_role",
        ),
        CheckConstraint(
            "status IN ('active', 'invited', 'deactivated')",
            name="ck_memberships_status",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_memberships_org_public"),
        UniqueConstraint("organization_id", "id", name="uq_memberships_org_id"),
        UniqueConstraint("organization_id", "subject_id", name="uq_memberships_org_subject"),
        UniqueConstraint("organization_id", "email", name="uq_memberships_org_email"),
        Index("ix_memberships_org_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(32), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class InvitationModel(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_invitations_version_positive"),
        CheckConstraint(
            "role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_invitations_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="ck_invitations_status",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_invitations_org_public"),
        UniqueConstraint(
            "provider_invitation_id",
            name="uq_invitations_provider_invitation",
        ),
        Index("ix_invitations_org_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(32), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    invited_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False
    )
    provider_invitation_id: Mapped[str | None] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
