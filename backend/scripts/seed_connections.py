from app.config import Settings
from app.integrations.connection_seed import deterministic_connection_seeds
from app.persistence.connection_repository import ConnectionRepository
from app.persistence.database import Database


def main() -> None:
    settings = Settings()
    if settings.environment == "production":
        raise RuntimeError("Deterministic connection seed is disabled in production.")
    if not settings.database_url:
        raise RuntimeError("SUPPORT_COPILOT_DATABASE_URL is required to seed demo connections.")

    database = Database(settings.database_url)
    try:
        seeds = deterministic_connection_seeds()
        with database.session() as session:
            repository = ConnectionRepository(session)
            for command in seeds:
                repository.seed(
                    organization_public_id="ORG-0001",
                    command=command,
                    correlation_id=f"seed:{command.public_id}",
                )
        print(f"{len(seeds)} deterministic connections are present for ORG-0001.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
