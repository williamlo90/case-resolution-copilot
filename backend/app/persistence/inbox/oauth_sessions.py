from datetime import datetime
from hashlib import sha256

from sqlalchemy import delete, select

from app.domain.inbox import (
    EncryptedCredential,
    InboxAuthorizationError,
    InboxCapability,
    OAuthSessionRecord,
)
from app.persistence.models import InboxOAuthSessionModel, utc_now

from ._base import InboxRepositoryBase


class InboxOAuthSessionRepository(InboxRepositoryBase):
    def create(
        self,
        *,
        organization_public_id: str,
        actor_public_id: str,
        session_public_id: str,
        provider: str,
        capabilities: tuple[InboxCapability, ...],
        return_path: str,
        state: str,
        verifier: EncryptedCredential,
        expires_at: datetime,
    ) -> OAuthSessionRecord:
        organization = self._organization(organization_public_id)
        actor = self._member(organization.id, actor_public_id)
        model = InboxOAuthSessionModel(
            public_id=session_public_id,
            organization_id=organization.id,
            actor_id=actor.id,
            provider=provider,
            requested_capabilities=[item.value for item in capabilities],
            return_path=return_path,
            state_hash=_state_hash(state),
            verifier_ciphertext=verifier.ciphertext,
            verifier_nonce=verifier.nonce,
            verifier_authentication_tag=verifier.authentication_tag,
            verifier_key_id=verifier.key_id,
            verifier_algorithm=verifier.algorithm,
            verifier_fingerprint=verifier.credential_fingerprint,
            safe_metadata={"capability_count": len(capabilities)},
            attempt_count=0,
            expires_at=expires_at,
            consumed_at=None,
            created_at=utc_now(),
        )
        self._session.add(model)
        self._session.flush()
        return _record(model)

    def consume(
        self,
        *,
        organization_public_id: str,
        actor_public_id: str,
        state: str,
        now: datetime,
    ) -> OAuthSessionRecord:
        organization = self._organization(organization_public_id)
        actor = self._member(organization.id, actor_public_id)
        model = self._session.scalar(
            select(InboxOAuthSessionModel)
            .where(InboxOAuthSessionModel.state_hash == _state_hash(state))
            .with_for_update()
        )
        if (
            model is None
            or model.organization_id != organization.id
            or model.actor_id != actor.id
            or model.consumed_at is not None
            or model.expires_at <= now
        ):
            raise InboxAuthorizationError(
                "The inbox sign-in session is invalid or expired. Start again."
            )
        model.attempt_count += 1
        model.consumed_at = now
        self._session.flush()
        return _record(model)

    def delete_expired(self, *, before: datetime, limit: int = 100) -> int:
        ids = list(
            self._session.scalars(
                select(InboxOAuthSessionModel.id)
                .where(InboxOAuthSessionModel.expires_at <= before)
                .order_by(InboxOAuthSessionModel.expires_at)
                .limit(limit)
            )
        )
        if not ids:
            return 0
        self._session.execute(
            delete(InboxOAuthSessionModel).where(InboxOAuthSessionModel.id.in_(ids))
        )
        return len(ids)


def _record(model: InboxOAuthSessionModel) -> OAuthSessionRecord:
    return OAuthSessionRecord(
        public_id=model.public_id,
        organization_id=model.organization_id,
        actor_id=model.actor_id,
        provider=model.provider,
        requested_capabilities=tuple(
            InboxCapability(value) for value in model.requested_capabilities
        ),
        return_path=model.return_path,
        verifier=EncryptedCredential(
            ciphertext=model.verifier_ciphertext,
            nonce=model.verifier_nonce,
            authentication_tag=model.verifier_authentication_tag,
            key_id=model.verifier_key_id,
            algorithm=model.verifier_algorithm,
            credential_fingerprint=model.verifier_fingerprint,
        ),
        expires_at=model.expires_at,
    )


def _state_hash(state: str) -> str:
    return sha256(state.encode("utf-8")).hexdigest()
