from contextlib import AbstractContextManager
from types import TracebackType

from sqlalchemy.orm import Session

from app.persistence.case_persistence.inbox import CaseInboxWriter
from app.persistence.database import Database
from app.ports.inbox_import_persistence import InboxCaseWriter, InboxMessageStore
from app.ports.inbox_sync_persistence import (
    InboxSyncJobStore,
    InboxSyncUnitOfWork,
    InboxSyncUnitOfWorkFactory,
)

from .messages import InboxMessageRepository
from .sync_jobs import InboxSyncJobRepository


class SqlAlchemyInboxSyncUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._context: AbstractContextManager[Session] | None = None
        self.jobs: InboxSyncJobStore
        self.cases: InboxCaseWriter
        self.messages: InboxMessageStore

    def __enter__(self) -> "SqlAlchemyInboxSyncUnitOfWork":
        self._context = self._database.session()
        session = self._context.__enter__()
        self.jobs = InboxSyncJobRepository(session)
        self.cases = CaseInboxWriter(session)
        self.messages = InboxMessageRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._context is None:
            raise RuntimeError("Inbox sync unit of work was not entered.")
        return self._context.__exit__(exc_type, exc_value, traceback)


class SqlAlchemyInboxSyncUnitOfWorkFactory(InboxSyncUnitOfWorkFactory):
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> InboxSyncUnitOfWork:
        return SqlAlchemyInboxSyncUnitOfWork(self._database)
