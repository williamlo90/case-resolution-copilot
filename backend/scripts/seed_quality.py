from app.config import Settings
from app.integrations.quality_seed import deterministic_quality_projections
from app.persistence.database import Database
from app.persistence.quality_repository import QualityRepository


def main() -> None:
    settings = Settings()
    if settings.environment == "production":
        raise RuntimeError("Deterministic quality seed is disabled in production.")
    if not settings.database_url:
        raise RuntimeError(
            "SUPPORT_COPILOT_DATABASE_URL is required to seed quality evidence."
        )

    database = Database(settings.database_url)
    try:
        with database.session() as session:
            repository = QualityRepository(session)
            seeds = deterministic_quality_projections()
            for seed in seeds:
                repository.upsert_projection(
                    organization_public_id="ORG-0001",
                    seed=seed,
                    correlation_id=f"quality-seed:{seed.case_public_id}:{seed.category.value}",
                )
        print(f"{len(seeds)} deterministic quality projections are present.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
