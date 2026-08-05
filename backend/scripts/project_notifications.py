from app.config import Settings
from app.persistence.database import Database
from app.services.notification_projector import OperationalNotificationProjector


def main() -> None:
    settings = Settings()
    if settings.environment == "production":
        raise RuntimeError(
            "The manual notification projector is disabled in production."
        )
    if not settings.database_url:
        raise RuntimeError(
            "SUPPORT_COPILOT_DATABASE_URL is required to project notifications."
        )

    database = Database(settings.database_url)
    try:
        with database.session() as session:
            projected = OperationalNotificationProjector(session).project(
                organization_public_id="ORG-0001"
            )
        print(f"{projected} operational notification targets were projected.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
