from sqlalchemy import select

from app.config import Settings
from app.persistence.database import Database
from app.persistence.models import MembershipModel, OrganizationModel
from app.persistence.settings_repository import OrganizationSettingsRepository

DEMO_MEMBERS = (
    ("USR-0001", "Maya Specialist", "maya.specialist@example.com", "specialist"),
    ("USR-0002", "Rina Supervisor", "rina.supervisor@example.com", "supervisor"),
    ("USR-0003", "Ari Administrator", "ari.administrator@example.com", "administrator"),
    ("USR-0004", "Nadia Auditor", "nadia.auditor@example.com", "auditor"),
)


def seed_identity(*, database_url: str | None, environment: str) -> None:
    if environment == "production":
        raise RuntimeError("Deterministic identity seed is disabled in production.")
    if not database_url:
        raise RuntimeError("SUPPORT_COPILOT_DATABASE_URL is required to seed demo identity.")

    database = Database(database_url)
    try:
        with database.session() as session:
            organization = session.scalar(
                select(OrganizationModel).where(OrganizationModel.public_id == "ORG-0001")
            )
            if organization is None:
                organization = OrganizationModel(
                    public_id="ORG-0001",
                    name="Northstar Cloud",
                    slug="northstar-cloud",
                )
                session.add(organization)
                session.flush()

            for public_id, name, email, role in DEMO_MEMBERS:
                existing = session.scalar(
                    select(MembershipModel).where(
                        MembershipModel.organization_id == organization.id,
                        MembershipModel.public_id == public_id,
                    )
                )
                if existing is None:
                    session.add(
                        MembershipModel(
                            public_id=public_id,
                            organization_id=organization.id,
                            subject_id=public_id,
                            name=name,
                            email=email,
                            role=role,
                            status="active",
                        )
                    )
            session.flush()
            OrganizationSettingsRepository(session).ensure_defaults(
                organization_public_id="ORG-0001"
            )
        print("Deterministic organization, four demo members, and default settings are present.")
    finally:
        database.dispose()


def main() -> None:
    settings = Settings()
    seed_identity(
        database_url=settings.database_url,
        environment=settings.environment,
    )


if __name__ == "__main__":
    main()
