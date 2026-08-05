from app.config import Settings
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database


def main() -> None:
    settings = Settings()
    if settings.environment == "production":
        raise RuntimeError("Deterministic case seed is disabled in production.")
    if not settings.database_url:
        raise RuntimeError("SUPPORT_COPILOT_DATABASE_URL is required to seed demo cases.")

    database = Database(settings.database_url)
    try:
        with database.session() as session:
            repository = CaseRepository(session)
            cases = DeterministicCaseSourceSimulator().fetch_cases()
            for command in cases:
                repository.seed_case(
                    organization_public_id="ORG-0001",
                    command=command,
                    correlation_id=f"seed:{command.public_id}",
                )
        print(f"{len(cases)} deterministic generic cases are present for ORG-0001.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
