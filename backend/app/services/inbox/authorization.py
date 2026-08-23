from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from pydantic import SecretStr

from app.domain.identity import ActorContext, Permission
from app.domain.inbox import (
    AccessCredential,
    AuthorizationCallback,
    AuthorizationRequest,
    InboxAuthorizationError,
    InboxAuthorizationResult,
    InboxAuthorizationStart,
    InboxCapability,
)
from app.ports.credentials import CredentialProtector
from app.ports.inbox import InboxAuthorizationGatewayResolver
from app.ports.inbox_authorization_persistence import (
    InboxAuthorizationUnitOfWorkFactory,
)
from app.security.authorization import require_permission


@dataclass(frozen=True, slots=True)
class InboxAuthorizationPolicy:
    adapter_key: str
    client_id: str
    redirect_uri: str
    scope_by_capability: dict[InboxCapability, str]
    initial_window_days: int
    initial_item_limit: int
    drafts_enabled: bool
    session_minutes: int = 10


class InboxAuthorizationService:
    def __init__(
        self,
        *,
        unit_of_work: InboxAuthorizationUnitOfWorkFactory,
        gateways: InboxAuthorizationGatewayResolver,
        credentials: CredentialProtector,
        policy: InboxAuthorizationPolicy,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._gateways = gateways
        self._credentials = credentials
        self._policy = policy

    def start(
        self,
        *,
        actor: ActorContext,
        include_drafts: bool,
        return_path: str,
        login_hint: str | None,
    ) -> InboxAuthorizationStart:
        require_permission(actor, Permission.CONNECTION_MANAGE)
        if include_drafts and not self._policy.drafts_enabled:
            raise InboxAuthorizationError("Inbox draft creation is not enabled.")
        safe_return_path = _safe_return_path(return_path)
        capabilities = (InboxCapability.READ_CONVERSATIONS,) + (
            (InboxCapability.CREATE_DRAFTS,) if include_drafts else ()
        )
        scopes = tuple(self._policy.scope_by_capability[item] for item in capabilities)
        session_public_id = f"OAS-{uuid4().hex[:16].upper()}"
        state = token_urlsafe(48)
        verifier = token_urlsafe(64)
        challenge = urlsafe_b64encode(sha256(verifier.encode("ascii")).digest()).decode(
            "ascii"
        ).rstrip("=")
        gateway = self._gateways.authorization(self._policy.adapter_key)
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self._policy.session_minutes)
        encrypted_verifier = self._credentials.encrypt(
            refresh_token=verifier,
            organization_id=actor.organization_id,
            connection_id=session_public_id,
            provider=gateway.provider_name,
        )
        with self._unit_of_work() as uow:
            uow.oauth_sessions.create(
                organization_public_id=actor.organization_id,
                actor_public_id=actor.actor_id,
                session_public_id=session_public_id,
                provider=gateway.provider_name,
                capabilities=capabilities,
                return_path=safe_return_path,
                state=state,
                verifier=encrypted_verifier,
                expires_at=expires_at,
            )
        return InboxAuthorizationStart(
            authorization_url=gateway.authorization_url(
                AuthorizationRequest(
                    client_id=self._policy.client_id,
                    redirect_uri=self._policy.redirect_uri,
                    scopes=scopes,
                    state=state,
                    code_challenge=challenge,
                    login_hint=login_hint,
                )
            ),
            expires_at=expires_at,
        )

    def complete(
        self,
        *,
        actor: ActorContext,
        state: str,
        code: str,
        correlation_id: str,
    ) -> InboxAuthorizationResult:
        require_permission(actor, Permission.CONNECTION_MANAGE)
        now = datetime.now(UTC)
        with self._unit_of_work() as uow:
            session = uow.oauth_sessions.consume(
                organization_public_id=actor.organization_id,
                actor_public_id=actor.actor_id,
                state=state,
                now=now,
            )
        gateway = self._gateways.authorization(self._policy.adapter_key)
        verifier = self._credentials.decrypt(
            envelope=session.verifier,
            organization_id=actor.organization_id,
            connection_id=session.public_id,
            provider=session.provider,
        )
        grant = gateway.exchange_code(
            AuthorizationCallback(
                code=SecretStr(code),
                redirect_uri=self._policy.redirect_uri,
                code_verifier=SecretStr(verifier),
            )
        )
        required_scopes = {
            self._policy.scope_by_capability[item]
            for item in session.requested_capabilities
        }
        if not required_scopes.issubset(set(grant.granted_scopes)):
            raise InboxAuthorizationError(
                "The inbox did not grant all requested capabilities."
            )
        account = self._gateways.reader(self._policy.adapter_key).get_account(
            AccessCredential(
                access_token=grant.access_token,
                expires_at=grant.expires_at,
            )
        )
        with self._unit_of_work() as uow:
            connection = uow.connections.connect(
                organization_id=session.organization_id,
                account_address=account.address,
                provider_account_id=account.provider_account_id,
                adapter_key=self._policy.adapter_key,
                read_capabilities=[InboxCapability.READ_CONVERSATIONS.value],
                write_capabilities=(
                    [InboxCapability.CREATE_DRAFTS.value]
                    if InboxCapability.CREATE_DRAFTS in session.requested_capabilities
                    else []
                ),
            )
            encrypted_refresh = self._credentials.encrypt(
                refresh_token=grant.refresh_token.get_secret_value(),
                organization_id=actor.organization_id,
                connection_id=connection.public_id,
                provider=gateway.provider_name,
            )
            uow.credentials.establish(
                connection=connection,
                account=account,
                provider=gateway.provider_name,
                granted_scopes=grant.granted_scopes,
                credential=encrypted_refresh,
                initial_window_days=self._policy.initial_window_days,
                initial_item_limit=self._policy.initial_item_limit,
                actor_id=actor.actor_id,
                correlation_id=correlation_id,
            )
        return InboxAuthorizationResult(
            connection_public_id=connection.public_id,
            account_address=account.address,
            return_path=session.return_path,
            granted_capabilities=session.requested_capabilities,
        )


def _safe_return_path(value: str) -> str:
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        raise InboxAuthorizationError("The inbox return path is invalid.")
    return value[:500]
