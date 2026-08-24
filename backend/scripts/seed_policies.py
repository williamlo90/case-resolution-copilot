from datetime import UTC, datetime

from app.config import Settings
from app.integrations.policy_source_simulator import DeterministicPolicySourceSimulator
from app.persistence.database import Database
from app.persistence.policy_repository import PolicyRepository
from app.security.authentication import DeterministicAuthProvider
from app.services.policy_service import PolicyService


def seed_policies(*, database_url: str | None, environment: str) -> None:
    if environment == "production":
        raise RuntimeError("Deterministic policy seed is disabled in production.")
    if not database_url:
        raise RuntimeError("SUPPORT_COPILOT_DATABASE_URL is required to seed governed policies.")

    database = Database(database_url)
    actor = DeterministicAuthProvider().authenticate("USR-0003")
    seeds = DeterministicPolicySourceSimulator().fetch_policies()
    created = 0
    try:
        with database.session() as session:
            repository = PolicyRepository(session)
            service = PolicyService(repository)
            for seed in seeds:
                if (
                    repository.get_workspace(
                        organization_public_id=actor.organization_id,
                        policy_public_id=seed.public_id,
                    )
                    is not None
                ):
                    continue
                workspace = service.create_policy(
                    actor=actor,
                    title=seed.title,
                    description=seed.description,
                    source_kind=seed.source_kind,
                    source_name=seed.source_name,
                    source_text=seed.source_text,
                    applicability=seed.applicability,
                    effective_from=seed.effective_from,
                    effective_to=None,
                    public_id=seed.public_id,
                    correlation_id=f"seed:{seed.public_id}",
                )
                workspace = service.submit_review(
                    actor=actor,
                    policy_id=seed.public_id,
                    version_number=1,
                    expected_policy_version=workspace.policy.version,
                    expected_version=workspace.versions[0].version.record_version,
                    correlation_id=f"seed:{seed.public_id}",
                )
                service.publish(
                    actor=actor,
                    policy_id=seed.public_id,
                    version_number=1,
                    expected_policy_version=workspace.policy.version,
                    expected_version=workspace.versions[0].version.record_version,
                    effective_from=seed.effective_from,
                    correlation_id=f"seed:{seed.public_id}",
                    now=datetime(2026, 7, 22, tzinfo=UTC),
                )
                created += 1
        print(f"{created} governed policies created; {len(seeds) - created} already existed.")
    finally:
        database.dispose()


def main() -> None:
    settings = Settings()
    seed_policies(
        database_url=settings.database_url,
        environment=settings.environment,
    )


if __name__ == "__main__":
    main()
