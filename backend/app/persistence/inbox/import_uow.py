from contextlib import AbstractContextManager
from types import TracebackType

from sqlalchemy.orm import Session

from app.persistence.case_persistence.inbox import CaseInboxWriter
from app.persistence.database import Database
from app.ports.inbox_import_persistence import (
    InboxCaseWriter,
    InboxImportUnitOfWork,
    InboxImportUnitOfWorkFactory,
    InboxMessageStore,
)

from .messages import InboxMessageRepository


class SqlAlchemyInboxImportUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._context: AbstractContextManager[Session] | None = None
        self.cases: InboxCaseWriter
        self.messages: InboxMessageStore

    def __enter__(self) -> "SqlAlchemyInboxImportUnitOfWork":
        self._context = self._database.session()
        session = self._context.__enter__()
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
            raise RuntimeError("Inbox import unit of work was not entered.")
        return self._context.__exit__(exc_type, exc_value, traceback)


class SqlAlchemyInboxImportUnitOfWorkFactory(InboxImportUnitOfWorkFactory):
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> InboxImportUnitOfWork:
        return SqlAlchemyInboxImportUnitOfWork(self._database)
