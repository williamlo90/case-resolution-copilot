from sqlalchemy import delete, select

from app.domain.connections import ConnectionRecord
from app.domain.inbox import (
    EncryptedCredential,
    InboxConflict,
    InboxConnectionProfileRecord,
    InboxCredentialRecord,
    InboxCredentialUnavailable,
    InboxImportMode,
    InboxNotFound,
    ProviderAccount,
)
from app.persistence.models import (
    ConnectionCredentialEnvelopeModel,
    InboxConnectionProfileModel,
    InboxSyncCheckpointModel,
    utc_now,
)

from ._base import InboxRepositoryBase


class InboxCredentialRepository(InboxRepositoryBase):
    def establish(
        self,
        *,
        connection: ConnectionRecord,
        account: ProviderAccount,
        provider: str,
        granted_scopes: tuple[str, ...],
        credential: EncryptedCredential,
        initial_window_days: int,
        initial_item_limit: int,
        actor_id: str,
        correlation_id: str,
    ) -> InboxConnectionProfileRecord:
        profile = self._session.scalar(
            select(InboxConnectionProfileModel).where(
                InboxConnectionProfileModel.organization_id
                == connection.organization_id,
                InboxConnectionProfileModel.connection_id == connection.id,
            )
        )
        now = utc_now()
        if profile is None:
            profile = InboxConnectionProfileModel(
                public_id=f"INP-{connection.public_id}",
                organization_id=connection.organization_id,
                connection_id=connection.id,
                provider_account_id=account.provider_account_id,
                account_address=account.address.casefold(),
                import_mode=InboxImportMode.MANUAL.value,
                label_filter=["INBOX"],
                initial_window_days=initial_window_days,
                initial_item_limit=initial_item_limit,
                watch_expires_at=None,
                last_successful_sync_at=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            self._session.add(profile)
        else:
            if (
                profile.provider_account_id != account.provider_account_id
                or profile.account_address.casefold() != account.address.casefold()
            ):
                raise InboxConflict(
                    "The authorized inbox does not match this connection's history."
                )
            profile.provider_account_id = account.provider_account_id
            profile.account_address = account.address.casefold()
            profile.import_mode = InboxImportMode.MANUAL.value
            profile.version += 1
            profile.updated_at = now

        stored = self._session.scalar(
            select(ConnectionCredentialEnvelopeModel).where(
                ConnectionCredentialEnvelopeModel.organization_id
                == connection.organization_id,
                ConnectionCredentialEnvelopeModel.connection_id == connection.id,
            )
        )
        if stored is None:
            stored = ConnectionCredentialEnvelopeModel(
                organization_id=connection.organization_id,
                connection_id=connection.id,
                created_at=now,
            )
            self._session.add(stored)
        else:
            stored.rotated_at = now
        stored.ciphertext = credential.ciphertext
        stored.provider = provider
        stored.nonce = credential.nonce
        stored.authentication_tag = credential.authentication_tag
        stored.key_id = credential.key_id
        stored.algorithm = credential.algorithm
        stored.granted_scopes = list(granted_scopes)
        stored.credential_fingerprint = credential.credential_fingerprint
        stored.expires_at = None
        stored.updated_at = now

        checkpoint = self._session.scalar(
            select(InboxSyncCheckpointModel).where(
                InboxSyncCheckpointModel.organization_id == connection.organization_id,
                InboxSyncCheckpointModel.connection_id == connection.id,
            )
        )
        if checkpoint is None:
            self._session.add(
                InboxSyncCheckpointModel(
                    public_id=f"ICP-{connection.public_id}",
                    organization_id=connection.organization_id,
                    connection_id=connection.id,
                    provider_history_id=account.history_id,
                    last_observed_history_id=account.history_id,
                    status="current",
                    consecutive_failures=0,
                    last_error_code=None,
                    last_attempt_at=now,
                    last_successful_sync_at=None,
                    last_recovery_at=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
        self._session.flush()
        self._audit(
            organization_id=connection.organization_id,
            event_type="inbox.connected",
            actor_id=actor_id,
            subject_id=connection.public_id,
            summary="Inbox connected and verified.",
            data={
                "account_address": account.address.casefold(),
                "capability_count": len(granted_scopes),
            },
            correlation_id=correlation_id,
        )
        return InboxConnectionProfileRecord.model_validate(profile)

    def get(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> InboxCredentialRecord:
        connection = self._connection(
            organization_public_id,
            connection_public_id,
        )
        row = self._session.execute(
            select(InboxConnectionProfileModel, ConnectionCredentialEnvelopeModel)
            .join(
                ConnectionCredentialEnvelopeModel,
                ConnectionCredentialEnvelopeModel.organization_id
                == InboxConnectionProfileModel.organization_id,
            )
            .where(
                InboxConnectionProfileModel.organization_id == connection.organization_id,
                InboxConnectionProfileModel.connection_id == connection.id,
                ConnectionCredentialEnvelopeModel.connection_id == connection.id,
            )
        ).one_or_none()
        if row is None:
            raise InboxCredentialUnavailable("The inbox needs to be connected again.")
        profile, stored = row
        return InboxCredentialRecord(
            organization_id=connection.organization_id,
            connection_id=connection.id,
            connection_public_id=connection.public_id,
            adapter_key=connection.adapter_key,
            provider=stored.provider,
            account_address=profile.account_address,
            import_mode=profile.import_mode,
            granted_scopes=tuple(stored.granted_scopes),
            credential=EncryptedCredential(
                ciphertext=stored.ciphertext,
                nonce=stored.nonce,
                authentication_tag=stored.authentication_tag,
                key_id=stored.key_id,
                algorithm=stored.algorithm,
                credential_fingerprint=stored.credential_fingerprint,
            ),
        )

    def set_import_mode(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
        mode: InboxImportMode,
        actor_id: str,
        correlation_id: str,
    ) -> InboxConnectionProfileRecord:
        connection = self._connection(
            organization_public_id,
            connection_public_id,
            for_update=True,
        )
        profile = self._session.scalar(
            select(InboxConnectionProfileModel)
            .where(
                InboxConnectionProfileModel.organization_id == connection.organization_id,
                InboxConnectionProfileModel.connection_id == connection.id,
            )
            .with_for_update()
        )
        if profile is None:
            raise InboxNotFound("The inbox profile was not found.")
        profile.import_mode = mode.value
        profile.version += 1
        profile.updated_at = utc_now()
        self._audit(
            organization_id=connection.organization_id,
            event_type="inbox.import_mode_changed",
            actor_id=actor_id,
            subject_id=connection.public_id,
            summary=(
                "Inbox import paused."
                if mode is InboxImportMode.PAUSED
                else "Inbox import resumed."
            ),
            data={"import_mode": mode.value},
            correlation_id=correlation_id,
        )
        self._session.flush()
        return InboxConnectionProfileRecord.model_validate(profile)

    def delete_credential(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
        actor_id: str,
        correlation_id: str,
    ) -> None:
        connection = self._connection(
            organization_public_id,
            connection_public_id,
            for_update=True,
        )
        self._session.execute(
            delete(ConnectionCredentialEnvelopeModel).where(
                ConnectionCredentialEnvelopeModel.organization_id
                == connection.organization_id,
                ConnectionCredentialEnvelopeModel.connection_id == connection.id,
            )
        )
        profile = self._session.scalar(
            select(InboxConnectionProfileModel).where(
                InboxConnectionProfileModel.organization_id == connection.organization_id,
                InboxConnectionProfileModel.connection_id == connection.id,
            )
        )
        if profile is not None:
            profile.import_mode = InboxImportMode.PAUSED.value
            profile.version += 1
            profile.updated_at = utc_now()
        self._audit(
            organization_id=connection.organization_id,
            event_type="inbox.disconnected",
            actor_id=actor_id,
            subject_id=connection.public_id,
            summary="Inbox disconnected; historical case evidence was preserved.",
            data={"credential_deleted": True},
            correlation_id=correlation_id,
        )
