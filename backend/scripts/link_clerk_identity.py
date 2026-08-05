import argparse
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.config import Settings
from app.persistence.database import Database
from app.persistence.models import (
    AuditEventModel,
    MembershipModel,
    OrganizationModel,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Link one Clerk user to one existing workspace membership."
    )
    parser.add_argument("--organization", default="ORG-0001")
    parser.add_argument("--member", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist the link. Without this flag the command is a dry run.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _arguments()
    settings = Settings()
    if settings.environment == "production":
        raise RuntimeError("Use a reviewed administrator workflow to link production identities.")
    if not settings.database_url:
        raise RuntimeError("SUPPORT_COPILOT_DATABASE_URL is required to link an identity.")

    subject_id = str(arguments.subject).strip()
    if not subject_id.startswith("user_"):
        raise RuntimeError("The Clerk subject must start with 'user_'.")

    database = Database(settings.database_url)
    try:
        with database.session() as session:
            organization = session.scalar(
                select(OrganizationModel).where(
                    OrganizationModel.public_id == arguments.organization
                )
            )
            if organization is None:
                raise RuntimeError("The workspace was not found.")

            member = session.scalar(
                select(MembershipModel).where(
                    MembershipModel.organization_id == organization.id,
                    MembershipModel.public_id == arguments.member,
                )
            )
            if member is None:
                raise RuntimeError("The workspace member was not found.")
            if member.status != "active":
                raise RuntimeError("Only an active workspace member can be linked.")

            existing = session.scalar(
                select(MembershipModel).where(
                    MembershipModel.subject_id == subject_id,
                    MembershipModel.id != member.id,
                )
            )
            if existing is not None:
                raise RuntimeError("The Clerk identity is already linked to another membership.")
            if member.subject_id == subject_id:
                print("The Clerk identity is already linked to this membership.")
                return
            if not arguments.apply:
                print(
                    "Dry run passed. Add --apply to link the Clerk identity to "
                    f"{member.public_id} in {organization.public_id}."
                )
                return

            member.subject_id = subject_id
            member.version += 1
            member.updated_at = datetime.now(UTC)
            session.add(
                AuditEventModel(
                    organization_id=organization.id,
                    task_id=None,
                    run_id=None,
                    event_type="membership.identity_linked",
                    actor_type="system",
                    actor_id="activation-cli",
                    subject_type="member",
                    subject_id=member.public_id,
                    summary="External identity linked to workspace membership.",
                    data={"identity_provider": "clerk"},
                    correlation_id=f"activation-{uuid4().hex}",
                )
            )
            session.flush()
            print(f"Clerk identity linked to {member.public_id} in {organization.public_id}.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
