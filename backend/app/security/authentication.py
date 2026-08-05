from collections.abc import Callable, Mapping
from typing import Protocol
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    ActorMembershipAmbiguous,
    ActorMembershipNotFound,
    ActorOrganizationContext,
    AuthenticationMode,
    InvitedIdentity,
    MemberRole,
    Permission,
)
from app.integrations.clerk_identity import (
    IdentityDirectoryUnavailable,
    InvitedIdentityNotFound,
)
from app.persistence.database import Database
from app.persistence.identity_repository import OrganizationRepository


class AuthenticationRequired(PermissionError):
    pass


class AuthenticationUnavailable(RuntimeError):
    pass


class WorkspaceAccessDenied(PermissionError):
    pass


class WorkspaceSelectionRequired(RuntimeError):
    pass


class AuthenticationRequest(Protocol):
    @property
    def headers(self) -> Mapping[str, str]: ...


class AuthProvider(Protocol):
    def authenticate(
        self,
        actor_id: str | None,
        *,
        request: AuthenticationRequest | None = None,
        session: Session | None = None,
    ) -> ActorContext: ...


class SessionSubjectVerifier(Protocol):
    def verify_subject(self, request: AuthenticationRequest) -> str: ...


class ActorResolver(Protocol):
    def resolve_actor(
        self,
        subject_id: str,
        *,
        session: Session | None = None,
    ) -> ActorContext: ...


class InvitedIdentityDirectory(Protocol):
    def get_invited_identity(self, subject_id: str) -> InvitedIdentity: ...


class ActorProvisioner(Protocol):
    def provision_actor(self, subject_id: str) -> ActorContext: ...


SessionTokenDecoder = Callable[[str, str], Mapping[str, object]]


def _decode_session_token(token: str, jwt_key: str) -> Mapping[str, object]:
    payload: object = jwt.decode(
        token,
        jwt_key,
        algorithms=["RS256"],
        options={"require": ["exp", "nbf", "sub"]},
    )
    if not isinstance(payload, dict):
        raise InvalidTokenError("The session token payload is invalid.")
    return {key: value for key, value in payload.items() if isinstance(key, str)}


def _bearer_token(headers: Mapping[str, str]) -> str:
    authorization = next(
        (value for key, value in headers.items() if key.lower() == "authorization"),
        "",
    )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise AuthenticationRequired("A valid sign-in session is required.")
    return parts[1]


class ClerkSessionVerifier:
    def __init__(
        self,
        *,
        jwt_key: str,
        authorized_parties: list[str],
        decoder: SessionTokenDecoder = _decode_session_token,
    ) -> None:
        self._jwt_key = jwt_key
        self._authorized_parties = frozenset(authorized_parties)
        self._decoder = decoder

    def verify_subject(self, request: AuthenticationRequest) -> str:
        token = _bearer_token(request.headers)
        try:
            payload = self._decoder(token, self._jwt_key)
        except InvalidTokenError:
            raise AuthenticationRequired("A valid sign-in session is required.") from None
        except Exception:
            raise AuthenticationUnavailable(
                "The identity provider could not verify the session."
            ) from None
        authorized_party = payload.get("azp")
        if authorized_party is not None and (
            not isinstance(authorized_party, str)
            or authorized_party not in self._authorized_parties
        ):
            raise AuthenticationRequired("The sign-in session came from an untrusted origin.")
        if payload.get("sts") == "pending":
            raise AuthenticationRequired("The sign-in session is not active yet.")
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationRequired("The sign-in session has no user identity.")
        return subject


class DatabaseActorResolver:
    def __init__(self, database: Database) -> None:
        self._database = database

    def resolve_actor(
        self,
        subject_id: str,
        *,
        session: Session | None = None,
    ) -> ActorContext:
        if session is not None:
            return OrganizationRepository(session).resolve_actor_by_subject(subject_id)
        with self._database.session() as session:
            return OrganizationRepository(session).resolve_actor_by_subject(subject_id)


class DatabaseInvitationProvisioner:
    def __init__(
        self,
        *,
        database: Database,
        directory: InvitedIdentityDirectory,
    ) -> None:
        self._database = database
        self._directory = directory

    def provision_actor(self, subject_id: str) -> ActorContext:
        try:
            identity = self._directory.get_invited_identity(subject_id)
        except InvitedIdentityNotFound:
            raise ActorMembershipNotFound(
                "The account is not linked to a pending workspace invitation."
            ) from None
        with self._database.session() as session:
            return OrganizationRepository(session).accept_invitation(
                identity=identity,
                correlation_id=f"auth-{uuid4()}",
            )


class ClerkAuthProvider:
    def __init__(
        self,
        *,
        verifier: SessionSubjectVerifier,
        resolver: ActorResolver,
        provisioner: ActorProvisioner | None = None,
    ) -> None:
        self._verifier = verifier
        self._resolver = resolver
        self._provisioner = provisioner

    def authenticate(
        self,
        actor_id: str | None,
        *,
        request: AuthenticationRequest | None = None,
        session: Session | None = None,
    ) -> ActorContext:
        del actor_id
        if request is None:
            raise AuthenticationRequired("A sign-in request is required.")
        subject_id = self._verifier.verify_subject(request)
        try:
            if session is None:
                return self._resolver.resolve_actor(subject_id)
            return self._resolver.resolve_actor(subject_id, session=session)
        except ActorMembershipNotFound:
            if self._provisioner is None:
                raise WorkspaceAccessDenied(
                    "The account is not linked to an active workspace."
                ) from None
            try:
                return self._provisioner.provision_actor(subject_id)
            except ActorMembershipNotFound:
                raise WorkspaceAccessDenied(
                    "The account is not linked to an active workspace."
                ) from None
            except ActorMembershipAmbiguous:
                raise WorkspaceSelectionRequired(
                    "Choose one workspace before continuing."
                ) from None
            except IdentityDirectoryUnavailable:
                raise AuthenticationUnavailable(
                    "The identity provider could not load the account."
                ) from None
            except Exception:
                raise AuthenticationUnavailable(
                    "The workspace membership could not be provisioned."
                ) from None
        except ActorMembershipAmbiguous:
            raise WorkspaceSelectionRequired("Choose one workspace before continuing.") from None
        except Exception:
            raise AuthenticationUnavailable(
                "The workspace membership could not be verified."
            ) from None


def _member(
    actor_id: str,
    name: str,
    role: MemberRole,
    *,
    organization_id: str = "ORG-0001",
) -> ActorContext:
    return ActorContext(
        actor_id=actor_id,
        organization_id=organization_id,
        name=name,
        kind=ActorKind.MEMBER,
        role=role,
        permissions=ROLE_PERMISSIONS[role],
        authentication_mode=AuthenticationMode.DETERMINISTIC_DEVELOPMENT,
        organization=ActorOrganizationContext(
            id=organization_id,
            name="Northstar Cloud",
            slug="northstar-cloud",
            version=1,
            locale="en-US",
            time_zone="Asia/Jakarta",
        ),
    )


DETERMINISTIC_ACTORS: Mapping[str, ActorContext] = {
    "USR-0001": _member("USR-0001", "Maya Specialist", MemberRole.SPECIALIST),
    "USR-0002": _member("USR-0002", "Rina Supervisor", MemberRole.SUPERVISOR),
    "USR-0003": _member("USR-0003", "Ari Administrator", MemberRole.ADMINISTRATOR),
    "USR-0004": _member("USR-0004", "Nadia Auditor", MemberRole.AUDITOR),
    "operator-1": _member("operator-1", "Compatibility Specialist", MemberRole.SPECIALIST),
    "reviewer-1": _member("reviewer-1", "Compatibility Supervisor", MemberRole.SUPERVISOR),
    "reviewer-2": _member("reviewer-2", "Second Compatibility Supervisor", MemberRole.SUPERVISOR),
    "SVC-0001": ActorContext(
        actor_id="SVC-0001",
        organization_id="ORG-0001",
        name="Deterministic workflow service",
        kind=ActorKind.SERVICE,
        role=None,
        permissions=frozenset(
            {
                Permission.SESSION_READ,
                Permission.CASE_READ,
                Permission.CASE_MANAGE,
                Permission.ACTION_READ,
                Permission.ACTION_EXECUTE,
                Permission.ACTION_RECONCILE,
            }
        ),
        authentication_mode=AuthenticationMode.DETERMINISTIC_DEVELOPMENT,
    ),
}


class DeterministicAuthProvider:
    def __init__(self, actors: Mapping[str, ActorContext] = DETERMINISTIC_ACTORS) -> None:
        self._actors = dict(actors)

    def authenticate(
        self,
        actor_id: str | None,
        *,
        request: AuthenticationRequest | None = None,
        session: Session | None = None,
    ) -> ActorContext:
        del request, session
        if not actor_id:
            raise AuthenticationRequired("A development actor identity is required.")
        actor = self._actors.get(actor_id)
        if actor is None:
            raise AuthenticationRequired("The development actor identity is not recognized.")
        return actor


class UnavailableProviderAuth:
    def authenticate(
        self,
        actor_id: str | None,
        *,
        request: AuthenticationRequest | None = None,
        session: Session | None = None,
    ) -> ActorContext:
        del actor_id, request, session
        raise AuthenticationUnavailable("The configured authentication provider is unavailable.")
