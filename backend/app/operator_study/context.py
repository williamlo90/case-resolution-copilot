from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.orm import Session

from app.analysis.deterministic_decision_engine import DecisionEngine
from app.domain.identity import ActorContext
from app.security.authentication import AuthenticationRequest, AuthProvider

# Only server code can set these. No browser-supplied impersonation header exists.
internal_actor: ContextVar[ActorContext | None] = ContextVar("study_actor", default=None)
manual_engine: ContextVar[DecisionEngine | None] = ContextVar("study_engine", default=None)


class StudyAuthProvider:
    def __init__(self, normal: AuthProvider) -> None:
        self.normal = normal

    def authenticate(
        self,
        actor_id: str | None,
        *,
        request: AuthenticationRequest | None = None,
        session: Session | None = None,
    ) -> ActorContext:
        override = internal_actor.get()
        if override is not None:
            return override
        return self.normal.authenticate(actor_id, request=request, session=session)
