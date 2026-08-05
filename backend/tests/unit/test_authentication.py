from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    ActorMembershipAmbiguous,
    ActorMembershipNotFound,
    AuthenticationMode,
    MemberRole,
    Permission,
)
from app.integrations.clerk_identity import IdentityDirectoryUnavailable
from app.security.authentication import (
    AuthenticationRequest,
    AuthenticationRequired,
    AuthenticationUnavailable,
    ClerkAuthProvider,
    ClerkSessionVerifier,
    DeterministicAuthProvider,
    WorkspaceAccessDenied,
    WorkspaceSelectionRequired,
)


@dataclass(frozen=True)
class StubRequest:
    headers: Mapping[str, str]


class StubTokenDecoder:
    def __init__(
        self,
        payload: Mapping[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {}
        self.error = error
        self.token: str | None = None
        self.jwt_key: str | None = None

    def __call__(self, token: str, jwt_key: str) -> Mapping[str, object]:
        self.token = token
        self.jwt_key = jwt_key
        if self.error is not None:
            raise self.error
        return self.payload


class StubVerifier:
    def __init__(self, subject_id: str) -> None:
        self.subject_id = subject_id

    def verify_subject(self, request: AuthenticationRequest) -> str:
        del request
        return self.subject_id


class StaticResolver:
    def __init__(self, actor: ActorContext) -> None:
        self.actor = actor
        self.subject_id: str | None = None

    def resolve_actor(
        self,
        subject_id: str,
        *,
        session: Session | None = None,
    ) -> ActorContext:
        del session
        self.subject_id = subject_id
        return self.actor


class MissingResolver:
    def resolve_actor(
        self,
        subject_id: str,
        *,
        session: Session | None = None,
    ) -> ActorContext:
        del subject_id, session
        raise ActorMembershipNotFound


class AmbiguousResolver:
    def resolve_actor(
        self,
        subject_id: str,
        *,
        session: Session | None = None,
    ) -> ActorContext:
        del subject_id, session
        raise ActorMembershipAmbiguous


class StubProvisioner:
    def __init__(
        self,
        actor: ActorContext | None = None,
        error: Exception | None = None,
    ) -> None:
        self.actor = actor
        self.error = error
        self.subject_id: str | None = None

    def provision_actor(self, subject_id: str) -> ActorContext:
        self.subject_id = subject_id
        if self.error is not None:
            raise self.error
        assert self.actor is not None
        return self.actor


def provider_actor() -> ActorContext:
    role = MemberRole.ADMINISTRATOR
    return ActorContext(
        actor_id="USR-0100",
        organization_id="ORG-0100",
        name="Provider Administrator",
        kind=ActorKind.MEMBER,
        role=role,
        permissions=ROLE_PERMISSIONS[role],
        authentication_mode=AuthenticationMode.PROVIDER,
    )


def test_deterministic_provider_resolves_server_owned_role_and_permissions() -> None:
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    assert actor.role is MemberRole.SPECIALIST
    assert actor.can(Permission.CASE_MANAGE)
    assert not actor.can(Permission.REVIEW_DECIDE)
    assert actor.organization_id == "ORG-0001"


@pytest.mark.parametrize("actor_id", [None, "", "USR-9999"])
def test_deterministic_provider_rejects_missing_or_unknown_identity(actor_id: str | None) -> None:
    with pytest.raises(AuthenticationRequired):
        DeterministicAuthProvider().authenticate(actor_id)


def test_supervisor_and_auditor_authority_are_distinct() -> None:
    provider = DeterministicAuthProvider()
    supervisor = provider.authenticate("USR-0002")
    auditor = provider.authenticate("USR-0004")

    assert supervisor.can(Permission.REVIEW_DECIDE)
    assert not supervisor.can(Permission.AUDIT_READ)
    assert auditor.can(Permission.AUDIT_READ)
    assert not auditor.can(Permission.REVIEW_DECIDE)


def test_clerk_verifier_accepts_only_session_tokens_and_returns_subject() -> None:
    decoder = StubTokenDecoder(
        {
            "sub": "user_123",
            "azp": "http://localhost:3000",
            "iss": "https://example.clerk.accounts.dev",
            "sid": "sess_123",
        }
    )
    verifier = ClerkSessionVerifier(
        jwt_key="test-public-key",
        authorized_parties=["http://localhost:3000"],
        decoder=decoder,
    )

    subject_id = verifier.verify_subject(
        StubRequest(headers={"Authorization": "Bearer stub-session-token"})
    )

    assert subject_id == "user_123"
    assert decoder.token == "stub-session-token"
    assert decoder.jwt_key == "test-public-key"


def test_clerk_verifier_validates_a_real_rs256_session_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user_123",
            "azp": "https://app.example.com",
            "iss": "https://example.clerk.accounts.dev",
            "sid": "sess_123",
            "nbf": now - timedelta(seconds=5),
            "exp": now + timedelta(minutes=1),
        },
        private_key,
        algorithm="RS256",
    )
    verifier = ClerkSessionVerifier(
        jwt_key=public_key.decode("ascii"),
        authorized_parties=["https://app.example.com"],
    )
    request = StubRequest(headers={"Authorization": f"Bearer {token}"})

    assert verifier.verify_subject(request) == "user_123"
    with pytest.raises(AuthenticationRequired):
        verifier.verify_subject(StubRequest(headers={"Authorization": f"Bearer {token}tampered"}))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "sub": "user_123",
            "iss": "https://example.clerk.accounts.dev",
            "sid": "sess_123",
            "azp": "https://untrusted.example.com",
        },
        {
            "sub": "user_123",
            "iss": "https://example.clerk.accounts.dev",
            "sid": "sess_123",
            "sts": "pending",
        },
        {
            "sub": "user_123",
            "iss": "https://example.clerk.accounts.dev",
        },
    ],
)
def test_clerk_verifier_rejects_subjectless_or_untrusted_sessions(
    payload: Mapping[str, object],
) -> None:
    verifier = ClerkSessionVerifier(
        jwt_key="test-public-key",
        authorized_parties=["http://localhost:3000"],
        decoder=StubTokenDecoder(payload),
    )

    with pytest.raises(AuthenticationRequired):
        verifier.verify_subject(StubRequest(headers={"Authorization": "Bearer stub-session-token"}))


def test_clerk_verifier_rejects_missing_or_invalid_bearer_tokens() -> None:
    verifier = ClerkSessionVerifier(
        jwt_key="test-public-key",
        authorized_parties=["http://localhost:3000"],
        decoder=StubTokenDecoder(error=InvalidTokenError("invalid")),
    )

    with pytest.raises(AuthenticationRequired):
        verifier.verify_subject(StubRequest(headers={}))
    with pytest.raises(AuthenticationRequired):
        verifier.verify_subject(
            StubRequest(headers={"Authorization": "Bearer invalid-session-token"})
        )


def test_clerk_verifier_allows_missing_authorized_party_claim() -> None:
    verifier = ClerkSessionVerifier(
        jwt_key="test-public-key",
        authorized_parties=["https://app.example.com"],
        decoder=StubTokenDecoder(
            {
                "sub": "user_123",
                "iss": "https://example.clerk.accounts.dev",
                "sid": "sess_123",
            }
        ),
    )

    assert verifier.verify_subject(
        StubRequest(headers={"Authorization": "Bearer stub-session-token"})
    ) == "user_123"


def test_clerk_verifier_hides_provider_failures() -> None:
    verifier = ClerkSessionVerifier(
        jwt_key="test-public-key",
        authorized_parties=["http://localhost:3000"],
        decoder=StubTokenDecoder(error=RuntimeError("provider failure")),
    )

    with pytest.raises(AuthenticationUnavailable):
        verifier.verify_subject(StubRequest(headers={"Authorization": "Bearer stub-session-token"}))


def test_clerk_provider_uses_database_owned_actor_context() -> None:
    resolver = StaticResolver(provider_actor())
    provider = ClerkAuthProvider(
        verifier=StubVerifier("user_123"),
        resolver=resolver,
    )

    actor = provider.authenticate(
        "untrusted-header-value",
        request=StubRequest(headers={"Authorization": "Bearer stub-session-token"}),
    )

    assert resolver.subject_id == "user_123"
    assert actor.actor_id == "USR-0100"
    assert actor.organization_id == "ORG-0100"
    assert actor.role is MemberRole.ADMINISTRATOR
    assert actor.authentication_mode is AuthenticationMode.PROVIDER


def test_clerk_provider_distinguishes_missing_and_ambiguous_membership() -> None:
    request = StubRequest(headers={"Authorization": "Bearer stub-session-token"})

    with pytest.raises(WorkspaceAccessDenied):
        ClerkAuthProvider(
            verifier=StubVerifier("user_missing"),
            resolver=MissingResolver(),
        ).authenticate(None, request=request)

    with pytest.raises(WorkspaceSelectionRequired):
        ClerkAuthProvider(
            verifier=StubVerifier("user_multiple"),
            resolver=AmbiguousResolver(),
        ).authenticate(None, request=request)


def test_clerk_provider_claims_a_verified_pending_invitation_once() -> None:
    provisioner = StubProvisioner(actor=provider_actor())
    provider = ClerkAuthProvider(
        verifier=StubVerifier("user_invited"),
        resolver=MissingResolver(),
        provisioner=provisioner,
    )

    actor = provider.authenticate(None, request=StubRequest(headers={}))

    assert actor.actor_id == "USR-0100"
    assert provisioner.subject_id == "user_invited"


def test_clerk_provider_reports_directory_outage_without_granting_access() -> None:
    provider = ClerkAuthProvider(
        verifier=StubVerifier("user_invited"),
        resolver=MissingResolver(),
        provisioner=StubProvisioner(
            error=IdentityDirectoryUnavailable("provider unavailable"),
        ),
    )

    with pytest.raises(AuthenticationUnavailable):
        provider.authenticate(None, request=StubRequest(headers={}))


def test_clerk_provider_translates_provisioning_ambiguity() -> None:
    provider = ClerkAuthProvider(
        verifier=StubVerifier("user_invited"),
        resolver=MissingResolver(),
        provisioner=StubProvisioner(error=ActorMembershipAmbiguous()),
    )

    with pytest.raises(WorkspaceSelectionRequired):
        provider.authenticate(None, request=StubRequest(headers={}))


def test_clerk_provider_hides_unexpected_provisioning_failure() -> None:
    provider = ClerkAuthProvider(
        verifier=StubVerifier("user_invited"),
        resolver=MissingResolver(),
        provisioner=StubProvisioner(error=RuntimeError("database unavailable")),
    )

    with pytest.raises(AuthenticationUnavailable):
        provider.authenticate(None, request=StubRequest(headers={}))
