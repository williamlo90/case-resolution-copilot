from app.config import Settings
from app.persistence.database import Database
from app.persistence.settings_repository import OrganizationSettingsRepository


def main() -> None:
    settings = Settings()
    if settings.environment == "production":
        raise RuntimeError("Deterministic settings seed is disabled in production.")
    if not settings.database_url:
        raise RuntimeError(
            "SUPPORT_COPILOT_DATABASE_URL is required to seed operational settings."
        )

    database = Database(settings.database_url)
    try:
        with database.session() as session:
            records = OrganizationSettingsRepository(session).ensure_defaults(
                organization_public_id="ORG-0001"
            )
        print(f"{len(records)} organization setting sections are present.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
