from contextlib import AbstractContextManager
from types import TracebackType

from sqlalchemy.orm import Session

from app.persistence.case_persistence.inbox_drafts import CaseDraftReader
from app.persistence.database import Database
from app.persistence.reviews.draft_authorization import (
    ReviewDraftAuthorizationReader,
)
from app.ports.inbox_draft_persistence import (
    CaseDraftStore,
    InboxDraftStore,
    InboxDraftUnitOfWork,
    InboxDraftUnitOfWorkFactory,
    ReviewDraftAuthorizationStore,
)

from .drafts import InboxDraftRepository


class SqlAlchemyInboxDraftUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._context: AbstractContextManager[Session] | None = None
        self.cases: CaseDraftStore
        self.reviews: ReviewDraftAuthorizationStore
        self.deliveries: InboxDraftStore

    def __enter__(self) -> "SqlAlchemyInboxDraftUnitOfWork":
        self._context = self._database.session()
        session = self._context.__enter__()
        self.cases = CaseDraftReader(session)
        self.reviews = ReviewDraftAuthorizationReader(session)
        self.deliveries = InboxDraftRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._context is None:
            raise RuntimeError("Inbox draft unit of work was not entered.")
        return self._context.__exit__(exc_type, exc_value, traceback)


class SqlAlchemyInboxDraftUnitOfWorkFactory(InboxDraftUnitOfWorkFactory):
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> InboxDraftUnitOfWork:
        return SqlAlchemyInboxDraftUnitOfWork(self._database)
