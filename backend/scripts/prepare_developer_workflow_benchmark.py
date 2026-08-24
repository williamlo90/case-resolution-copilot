from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.exc import SQLAlchemyError

from scripts.seed_developer_workflow_benchmark import seed_benchmark_fixtures
from scripts.seed_identity import seed_identity
from scripts.seed_policies import seed_policies

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env.test.local"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class BenchmarkTarget(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        env_file_encoding="utf-8",
    )

    test_database_url: SecretStr
    test_database_scope: Literal["disposable"]
    test_database_endpoint_id: str


def load_benchmark_target(env_file: Path) -> tuple[str, str]:
    if not env_file.is_file():
        raise ValueError(f"Benchmark env file not found: {env_file}")
    target = BenchmarkTarget(_env_file=env_file)
    database_url = target.test_database_url.get_secret_value()
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    elif not database_url.startswith("postgresql+psycopg://"):
        raise ValueError("TEST_DATABASE_URL must be a PostgreSQL connection string.")

    endpoint_id = target.test_database_endpoint_id
    if not re.fullmatch(r"ep-[a-z0-9-]+", endpoint_id):
        raise ValueError("TEST_DATABASE_ENDPOINT_ID is invalid.")
    parsed = urlsplit(database_url)
    host = parsed.hostname or ""
    actual_endpoint_id = host.split(".", 1)[0]
    if (
        actual_endpoint_id != endpoint_id
        or "-pooler" in host
        or not re.fullmatch(r"ep-.+\.neon\.tech", host)
    ):
        raise ValueError("TEST_DATABASE_URL must use the matching direct Neon endpoint.")
    if parse_qs(parsed.query).get("sslmode") != ["require"]:
        raise ValueError("TEST_DATABASE_URL must require TLS.")
    return database_url, endpoint_id


def upgrade_benchmark_schema(database_url: str) -> None:
    variable = "SUPPORT_COPILOT_DATABASE_URL"
    previous = os.environ.get(variable)
    os.environ[variable] = database_url
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the six-case benchmark into a disposable Neon branch."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--confirm-disposable-database", action="store_true")
    arguments = parser.parse_args()
    if not arguments.confirm_disposable_database:
        parser.error(
            "Pass --confirm-disposable-database only after verifying the Neon branch is disposable."
        )

    database_url, _ = load_benchmark_target(arguments.env_file.resolve())
    print("Validated disposable Neon benchmark target.")
    try:
        upgrade_benchmark_schema(database_url)
        seed_identity(database_url=database_url, environment="test")
        seed_policies(database_url=database_url, environment="test")
        seed_benchmark_fixtures(
            database_url=database_url,
            environment="test",
            acknowledged=True,
        )
    except SQLAlchemyError:
        raise SystemExit(
            "Benchmark database connection failed. Replace TEST_DATABASE_URL with a fresh "
            "direct connection string from the same disposable Neon branch, then retry."
        ) from None


if __name__ == "__main__":
    main()
