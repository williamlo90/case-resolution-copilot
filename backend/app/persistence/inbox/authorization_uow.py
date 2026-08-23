from contextlib import AbstractContextManager
from types import TracebackType

from sqlalchemy.orm import Session

from app.persistence.connection_persistence.inbox import InboxConnectionWriter
from app.persistence.database import Database
from app.ports.inbox_authorization_persistence import (
    InboxAuthorizationUnitOfWork,
    InboxAuthorizationUnitOfWorkFactory,
    InboxConnectionStore,
    InboxCredentialStore,
    InboxOAuthSessionStore,
)

from .credentials import InboxCredentialRepository
from .oauth_sessions import InboxOAuthSessionRepository


class SqlAlchemyInboxAuthorizationUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._context: AbstractContextManager[Session] | None = None
        self.oauth_sessions: InboxOAuthSessionStore
        self.credentials: InboxCredentialStore
        self.connections: InboxConnectionStore

    def __enter__(self) -> "SqlAlchemyInboxAuthorizationUnitOfWork":
        self._context = self._database.session()
        session = self._context.__enter__()
        self.oauth_sessions = InboxOAuthSessionRepository(session)
        self.credentials = InboxCredentialRepository(session)
        self.connections = InboxConnectionWriter(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._context is None:
            raise RuntimeError("Inbox authorization unit of work was not entered.")
        return self._context.__exit__(exc_type, exc_value, traceback)


class SqlAlchemyInboxAuthorizationUnitOfWorkFactory(
    InboxAuthorizationUnitOfWorkFactory
):
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> InboxAuthorizationUnitOfWork:
        return SqlAlchemyInboxAuthorizationUnitOfWork(self._database)
