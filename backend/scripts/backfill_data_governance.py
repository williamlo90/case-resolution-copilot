import argparse

from app.config import Settings
from app.persistence.data_governance_repository import DataGovernanceRepository
from app.persistence.database import Database


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or apply non-destructive case retention state."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write governance rows. The default is a dry run.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _arguments()
    settings = Settings()
    if settings.environment == "production":
        raise RuntimeError("The deterministic governance backfill is disabled in production.")
    if not settings.database_url:
        raise RuntimeError(
            "SUPPORT_COPILOT_DATABASE_URL is required to backfill governance state."
        )

    database = Database(settings.database_url)
    try:
        with database.session() as session:
            planned, written = DataGovernanceRepository(session).backfill(
                organization_public_id="ORG-0001",
                apply=bool(arguments.apply),
            )
        mode = "apply" if arguments.apply else "dry run"
        print(f"{mode}: {planned} case rows planned; {written} rows written.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
