from contextlib import AbstractContextManager
from types import TracebackType

from sqlalchemy.orm import Session

from app.persistence.database import Database
from app.ports.policy_indexing import (
    PolicyIndexStore,
    PolicyIndexUnitOfWork,
    PolicyIndexUnitOfWorkFactory,
)

from .jobs import PolicyIndexRepository


class SqlAlchemyPolicyIndexUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._context: AbstractContextManager[Session] | None = None
        self.jobs: PolicyIndexStore

    def __enter__(self) -> "SqlAlchemyPolicyIndexUnitOfWork":
        self._context = self._database.session()
        session = self._context.__enter__()
        self.jobs = PolicyIndexRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._context is None:
            raise RuntimeError("Policy index unit of work was not entered.")
        return self._context.__exit__(exc_type, exc_value, traceback)


class SqlAlchemyPolicyIndexUnitOfWorkFactory(PolicyIndexUnitOfWorkFactory):
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> PolicyIndexUnitOfWork:
        return SqlAlchemyPolicyIndexUnitOfWork(self._database)
