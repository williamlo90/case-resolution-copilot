from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2},
        )
        self._session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._session_factory() as session, session.begin():
            yield session

    def is_ready(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            return False
        return True

    def dispose(self) -> None:
        self.engine.dispose()
