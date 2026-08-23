from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class InboxConnectionProfileModel(Base):
    __tablename__ = "inbox_connection_profiles"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_inbox_profiles_version"),
        CheckConstraint(
            "import_mode IN ('paused', 'manual', 'scheduled')",
            name="ck_inbox_profiles_import_mode",
        ),
        CheckConstraint(
            "initial_window_days BETWEEN 1 AND 30",
            name="ck_inbox_profiles_window",
        ),
        CheckConstraint(
            "initial_item_limit BETWEEN 1 AND 100",
            name="ck_inbox_profiles_item_limit",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_inbox_profiles_org_id",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_inbox_profiles_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            name="uq_inbox_profiles_org_connection",
        ),
        UniqueConstraint(
            "organization_id",
            "provider_account_id",
            name="uq_inbox_profiles_org_provider_account",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_inbox_profiles_org_connection",
            ondelete="CASCADE",
        ),
        Index(
            "ix_inbox_profiles_org_mode",
            "organization_id",
            "import_mode",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(500), nullable=False)
    account_address: Mapped[str] = mapped_column(String(320), nullable=False)
    import_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    label_filter: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    initial_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_item_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    watch_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ConnectionCredentialEnvelopeModel(Base):
    __tablename__ = "connection_credential_envelopes"
    __table_args__ = (
        CheckConstraint(
            "algorithm = 'AES-256-GCM'",
            name="ck_connection_credentials_algorithm",
        ),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            name="uq_connection_credentials_org_connection",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_connection_credentials_org_connection",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    authentication_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    credential_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class InboxOAuthSessionModel(Base):
    __tablename__ = "inbox_oauth_sessions"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="ck_inbox_oauth_attempt_count"),
        CheckConstraint(
            "expires_at <= created_at + INTERVAL '10 minutes'",
            name="ck_inbox_oauth_lifetime",
        ),
        UniqueConstraint("state_hash", name="uq_inbox_oauth_state_hash"),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_inbox_oauth_org_public",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_inbox_oauth_org_actor",
            ondelete="CASCADE",
        ),
        Index("ix_inbox_oauth_expires", "expires_at", "consumed_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    return_path: Mapped[str] = mapped_column(String(500), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    verifier_nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier_authentication_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier_algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    verifier_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
