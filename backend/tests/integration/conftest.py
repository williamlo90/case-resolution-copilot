import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config

from app.persistence.database import Database


class _RedactedDatabaseUrl(str):
    def __repr__(self) -> str:
        return "<redacted TEST_DATABASE_URL>"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests.")
    return _RedactedDatabaseUrl(value)


@pytest.fixture(scope="session")
def migrated_database(test_database_url: str) -> Iterator[None]:
    if os.getenv("SUPPORT_COPILOT_ALLOW_DESTRUCTIVE_TEST_DATABASE") != "1":
        pytest.fail(
            "Migration rehearsal requires the guarded disposable-database runner."
        )

    previous = os.environ.get("SUPPORT_COPILOT_DATABASE_URL")
    os.environ["SUPPORT_COPILOT_DATABASE_URL"] = test_database_url
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("SUPPORT_COPILOT_DATABASE_URL", None)
        else:
            os.environ["SUPPORT_COPILOT_DATABASE_URL"] = previous


@pytest.fixture
def database(test_database_url: str, migrated_database: None) -> Iterator[Database]:
    database = Database(test_database_url)
    try:
        yield database
    finally:
        database.dispose()
