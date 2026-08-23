import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.persistence.database import Database
from app.retrieval.ingest import ingest_policy


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
        pytest.fail("Migration rehearsal requires the guarded disposable-database runner.")

    previous = os.environ.get("SUPPORT_COPILOT_DATABASE_URL")
    os.environ["SUPPORT_COPILOT_DATABASE_URL"] = test_database_url
    cleanup_database = Database(test_database_url)
    try:
        _truncate_application_tables(cleanup_database)
    finally:
        cleanup_database.dispose()
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        cleanup_database = Database(test_database_url)
        try:
            _truncate_application_tables(
                cleanup_database,
                preserve_migration_seeds=True,
            )
        finally:
            cleanup_database.dispose()
        if previous is None:
            os.environ.pop("SUPPORT_COPILOT_DATABASE_URL", None)
        else:
            os.environ["SUPPORT_COPILOT_DATABASE_URL"] = previous


@pytest.fixture
def database(test_database_url: str, migrated_database: None) -> Iterator[Database]:
    database = Database(test_database_url)
    _truncate_application_tables(database, preserve_migration_seeds=True)

    source_root = Path(__file__).resolve().parents[2] / "policies" / "source"
    for source in sorted(source_root.glob("*.json")):
        ingest_policy(database, source)
    try:
        yield database
    finally:
        database.dispose()


def _truncate_application_tables(
    database: Database,
    *,
    preserve_migration_seeds: bool = False,
) -> None:
    excluded = {"alembic_version"}
    if preserve_migration_seeds:
        excluded.add("policy_embedding_profiles")
    table_names = sorted(
        name for name in inspect(database.engine).get_table_names() if name not in excluded
    )
    if table_names:
        preparer = database.engine.dialect.identifier_preparer
        quoted = ", ".join(preparer.quote(name) for name in table_names)
        with database.session() as session:
            session.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))
